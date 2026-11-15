from types import SimpleNamespace

import pytest

from pipeline.llm import ClienteClaude, ClienteGemini, ErroLLM, _sobrecarga, _validar, obter_cliente
from pipeline.schemas import CardapioBruto, EnriquecimentoLote


# ---------- _validar: a resposta do modelo precisa bater com o esquema ----------

def test_validar_aceita_json_em_texto():
    resultado = _validar('{"estabelecimento": "Zé", "itens": []}', CardapioBruto)
    assert resultado.estabelecimento == "Zé"


def test_validar_aceita_dicionario():
    assert _validar({"itens": []}, EnriquecimentoLote).itens == []


def test_validar_resposta_vazia_vira_erro():
    with pytest.raises(ErroLLM, match="vazia"):
        _validar("", CardapioBruto)


def test_validar_tag_fora_da_lista_vira_erro():
    with pytest.raises(ErroLLM):
        _validar({"itens": [{"nome": "X", "descricao": "Y", "tags": ["saudavel"]}]}, EnriquecimentoLote)


# ---------- obter_cliente: escolha do provedor pelo ambiente ----------

def test_sem_chave_da_erro_claro():
    with pytest.raises(ErroLLM, match="GEMINI_API_KEY"):
        obter_cliente()


def test_gemini_e_o_padrao(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "chave-falsa")
    assert isinstance(obter_cliente(), ClienteGemini)


def test_claude_pela_variavel_provedor(monkeypatch):
    monkeypatch.setenv("PROVEDOR", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-falsa")
    assert isinstance(obter_cliente(), ClienteClaude)


def test_provedor_desconhecido(monkeypatch):
    monkeypatch.setenv("PROVEDOR", "openai")
    with pytest.raises(ErroLLM, match="desconhecido"):
        obter_cliente()


# ---------- ClienteGemini: troca de modelo quando o principal está lotado ----------

class _ModelsFalso:
    """Imita client.models: cada modelo da lista `lotados` responde 503."""

    def __init__(self, lotados=(), erro=None):
        self.lotados = set(lotados)
        self.erro = erro
        self.pedidos: list[str] = []

    def generate_content(self, model, contents, config):
        self.pedidos.append(model)
        if self.erro:
            raise self.erro
        if model in self.lotados:
            raise RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand.")
        return SimpleNamespace(text='{"itens": []}')


def _gemini(models: _ModelsFalso) -> ClienteGemini:
    cliente = ClienteGemini("chave-falsa", "modelo-a")
    cliente.modelos = ["modelo-a", "modelo-b"]
    cliente._cliente = SimpleNamespace(models=models)
    return cliente


def test_modelo_lotado_usa_o_reserva():
    models = _ModelsFalso(lotados={"modelo-a"})
    cliente = _gemini(models)
    cliente.gerar("p", EnriquecimentoLote)
    assert models.pedidos == ["modelo-a", "modelo-b"]
    assert cliente.modelo == "modelo-b"


def test_todos_lotados_vira_erro_llm():
    with pytest.raises(ErroLLM, match="503"):
        _gemini(_ModelsFalso(lotados={"modelo-a", "modelo-b"})).gerar("p", EnriquecimentoLote)


def test_chave_invalida_nao_tenta_outro_modelo():
    models = _ModelsFalso(erro=RuntimeError("400 API key not valid"))
    with pytest.raises(ErroLLM):
        _gemini(models).gerar("p", EnriquecimentoLote)
    assert models.pedidos == ["modelo-a"]


def test_identifica_erros_passageiros():
    assert _sobrecarga(RuntimeError("503 UNAVAILABLE"))
    assert _sobrecarga(RuntimeError("429 RESOURCE_EXHAUSTED"))
    assert not _sobrecarga(RuntimeError("400 INVALID_ARGUMENT"))
