"""Adaptadores de LLM: Gemini (padrão, gratuito) e Claude (alternativa).

O resto do código só conhece `ClienteLLM.gerar(prompt, esquema, imagem)`.
Trocar de provedor é mudar a variável PROVEDOR, sem tocar nas etapas.
Os dois adaptadores pedem saída estruturada e validam com Pydantic: se a
resposta não bater com o esquema, levantam ErroLLM.
"""

import base64
import os
from typing import Protocol, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

# Medido em 15/11/2026 com a mesma foto: 3.6-flash fez tudo em ~9 s;
# 3.8-flash estava lotado (erro 503) e passava de 1 minuto por chamada.
MODELO_PADRAO_GEMINI = "gemini-3.6-flash"
MODELO_PADRAO_CLAUDE = "claude-haiku-5-5"


class ErroLLM(Exception):
    """Falha ao chamar o LLM ou resposta fora do formato pedido."""


class ClienteLLM(Protocol):
    modelo: str

    def gerar(self, prompt: str, esquema: type[T], imagem: bytes | None = None) -> T: ...


def _validar(dado: str | dict | None, esquema: type[T]) -> T:
    if not dado:
        raise ErroLLM("O modelo devolveu uma resposta vazia.")
    try:
        if isinstance(dado, str):
            return esquema.model_validate_json(dado)
        return esquema.model_validate(dado)
    except ValidationError as erro:
        raise ErroLLM(f"A resposta não bate com o formato {esquema.__name__}: {erro}") from erro


def _sobrecarga(erro: Exception) -> bool:
    """Erros passageiros do servidor: modelo lotado, cota por minuto, tempo esgotado."""
    texto = str(erro).upper()
    return any(m in texto for m in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "TIMEOUT", "TIMED OUT", "DEADLINE"))


class ClienteGemini:
    # Copiar texto e sugerir tags não pede raciocínio longo: nível baixo deixa a
    # resposta mais rápida. (MINIMAL não é aceito pelo gemini-3.8-flash.)
    RACIOCINIO = "LOW"
    # Se o modelo principal estiver lotado (erro 503), tenta o reserva.
    MODELO_RESERVA = "gemini-3.8-flash"

    def __init__(self, chave: str, modelo: str):
        from google import genai
        from google.genai import types

        # Sem isto, o SDK repete sozinho até 5 vezes com espera de até 60 s
        # quando o servidor está lotado: foram 3,5 minutos num único teste.
        self._cliente = genai.Client(
            api_key=chave,
            http_options=types.HttpOptions(
                timeout=30_000,  # milissegundos; uma chamada normal leva ~5 s
                retry_options=types.HttpRetryOptions(attempts=2, max_delay=5),
            ),
        )
        self.modelo = modelo
        self.modelos = list(dict.fromkeys([modelo, self.MODELO_RESERVA]))
        self._com_raciocinio = True

    def _config(self, esquema: type[BaseModel]):
        from google.genai import types

        extra = {}
        if self._com_raciocinio:
            extra["thinking_config"] = types.ThinkingConfig(thinking_level=self.RACIOCINIO)
        return types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=esquema,
            **extra,
        )

    def gerar(self, prompt: str, esquema: type[T], imagem: bytes | None = None) -> T:
        from google.genai import types

        partes: list = []
        if imagem is not None:
            partes.append(types.Part.from_bytes(data=imagem, mime_type="image/jpeg"))
        partes.append(prompt)

        ultimo_erro: Exception | None = None
        for modelo in self.modelos:
            try:
                resposta = self._chamar(modelo, partes, esquema)
            except Exception as erro:
                ultimo_erro = erro
                if _sobrecarga(erro):
                    continue  # modelo lotado: tenta o próximo da lista
                break  # chave inválida, pedido errado: não adianta tentar outro
            self.modelo = modelo  # registra qual modelo respondeu
            return _validar(resposta.text, esquema)
        raise ErroLLM(f"Falha ao chamar o Gemini: {ultimo_erro}") from ultimo_erro

    def _chamar(self, modelo: str, partes: list, esquema: type[BaseModel]):
        try:
            return self._cliente.models.generate_content(
                model=modelo, contents=partes, config=self._config(esquema)
            )
        except Exception as erro:
            # Modelo que não aceita o nível de raciocínio: tenta de novo sem ele.
            if self._com_raciocinio and "thinking" in str(erro).lower():
                self._com_raciocinio = False
                return self._cliente.models.generate_content(
                    model=modelo, contents=partes, config=self._config(esquema)
                )
            raise


class ClienteClaude:
    def __init__(self, chave: str, modelo: str):
        import anthropic

        self._cliente = anthropic.Anthropic(api_key=chave)
        self.modelo = modelo

    def gerar(self, prompt: str, esquema: type[T], imagem: bytes | None = None) -> T:
        conteudo: list[dict] = []
        if imagem is not None:
            conteudo.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.b64encode(imagem).decode(),
                },
            })
        conteudo.append({"type": "text", "text": prompt})
        # Saída estruturada via ferramenta obrigatória: o Claude preenche o esquema.
        ferramenta = {
            "name": "responder",
            "description": "Devolve a resposta no formato pedido.",
            "input_schema": esquema.model_json_schema(),
        }
        try:
            resposta = self._cliente.messages.create(
                model=self.modelo,
                max_tokens=8000,
                tools=[ferramenta],
                tool_choice={"type": "tool", "name": "responder"},
                messages=[{"role": "user", "content": conteudo}],
            )
        except Exception as erro:
            raise ErroLLM(f"Falha ao chamar o Claude: {erro}") from erro
        for bloco in resposta.content:
            if bloco.type == "tool_use":
                return _validar(bloco.input, esquema)
        raise ErroLLM("O Claude não devolveu a resposta estruturada.")


def obter_cliente() -> ClienteLLM:
    """Cria o cliente a partir do .env (local) ou dos Secrets (Streamlit Cloud)."""
    load_dotenv()
    provedor = (os.getenv("PROVEDOR") or "gemini").strip().lower()
    modelo = (os.getenv("MODELO") or "").strip()

    if provedor == "gemini":
        chave = os.getenv("GEMINI_API_KEY")
        if not chave:
            raise ErroLLM("Falta GEMINI_API_KEY no .env (ou nos Secrets do Streamlit).")
        return ClienteGemini(chave, modelo or MODELO_PADRAO_GEMINI)

    if provedor == "anthropic":
        chave = os.getenv("ANTHROPIC_API_KEY")
        if not chave:
            raise ErroLLM("PROVEDOR=anthropic, mas falta ANTHROPIC_API_KEY.")
        return ClienteClaude(chave, modelo or MODELO_PADRAO_CLAUDE)

    raise ErroLLM(f"PROVEDOR desconhecido: '{provedor}'. Use 'gemini' ou 'anthropic'.")
