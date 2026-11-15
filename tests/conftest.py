"""Peças compartilhadas pelos testes.

Nenhum teste chama a API de verdade: as chaves são apagadas do ambiente e o
.env não é lido. O LLM é sempre o `LLMFalso`, que devolve respostas prontas.
"""

from io import BytesIO

import pytest
from PIL import Image

from pipeline.llm import ErroLLM
from pipeline.schemas import CardapioBruto, EnriquecimentoLote


@pytest.fixture(autouse=True)
def sem_chaves(monkeypatch):
    """Garante que nenhum teste use a chave real do .env."""
    for nome in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "PROVEDOR", "MODELO"):
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setattr("pipeline.llm.load_dotenv", lambda *a, **k: None)


class LLMFalso:
    """Imita o ClienteLLM: devolve o que foi configurado e anota as chamadas."""

    modelo = "falso"

    def __init__(self, bruto: dict | None = None, enriquecimento: dict | None = None,
                 falhar_extrator: bool = False, falhar_enriquecedor: bool = False):
        self.bruto = bruto or {"estabelecimento": None, "itens": []}
        self.enriquecimento = enriquecimento or {"itens": []}
        self.falhar_extrator = falhar_extrator
        self.falhar_enriquecedor = falhar_enriquecedor
        self.chamadas: list[tuple[str, bool]] = []  # (esquema, veio com imagem?)

    def gerar(self, prompt, esquema, imagem=None):
        self.chamadas.append((esquema.__name__, imagem is not None))
        if esquema is CardapioBruto:
            if self.falhar_extrator:
                raise ErroLLM("extrator falhou")
            return CardapioBruto.model_validate(self.bruto)
        if esquema is EnriquecimentoLote:
            if self.falhar_enriquecedor:
                raise ErroLLM("enriquecedor falhou")
            return EnriquecimentoLote.model_validate(self.enriquecimento)
        raise AssertionError(f"esquema inesperado: {esquema}")


@pytest.fixture
def foto_png() -> bytes:
    """PNG grande e com transparência, para testar a preparação da imagem."""
    buffer = BytesIO()
    Image.new("RGBA", (3000, 2000), (255, 0, 0, 128)).save(buffer, format="PNG")
    return buffer.getvalue()
