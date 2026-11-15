import pytest
from conftest import LLMFalso

from pipeline.llm import ErroLLM
from pipeline.orquestrador import processar
from pipeline.schemas import Tag

BRUTO = {
    "estabelecimento": "LANCHONETE DO ZÉ",
    "itens": [
        {"nome": "X-BURGUER", "preco_texto": "R$ 25,9", "categoria": "LANCHES"},
        {"nome": "X-BURGUER", "preco_texto": "R$ 25,9", "categoria": "LANCHES"},
        {"nome": "Pizza Calabresa", "preco_texto": "P 30,00 / G 45,00", "categoria": "Pizzas"},
        {"nome": "Suco de Laranja ....", "preco_texto": "8", "categoria": "Bebidas"},
    ],
}
ENRIQUECIMENTO = {"itens": [
    {"nome": "X-Burguer", "descricao": "Hambúrguer com queijo.", "tags": ["contem_lactose"]},
    {"nome": "Suco de Laranja", "descricao": "Suco de laranja.", "tags": ["bebida_sem_alcool", "bebida_alcoolica"]},
]}


def test_caminho_completo(foto_png):
    llm = LLMFalso(bruto=BRUTO, enriquecimento=ENRIQUECIMENTO)
    cardapio = processar(foto_png, cliente=llm)

    assert cardapio.estabelecimento == "Lanchonete do Zé"
    assert [i.nome for i in cardapio.itens] == ["X-Burguer", "Pizza Calabresa", "Suco de Laranja"]
    assert cardapio.itens[0].tags == [Tag.CONTEM_LACTOSE]
    assert sorted(p.tipo for p in cardapio.problemas) == ["preco_ausente", "tags_conflitantes"]
    assert cardapio.revisao_humana is True
    assert cardapio.enriquecido is True


def test_extrator_recebe_imagem_e_enriquecedor_nao(foto_png):
    llm = LLMFalso(bruto=BRUTO, enriquecimento=ENRIQUECIMENTO)
    processar(foto_png, cliente=llm)
    assert llm.chamadas == [("CardapioBruto", True), ("EnriquecimentoLote", False)]


def test_tempos_de_cada_etapa(foto_png):
    tempos = processar(foto_png, cliente=LLMFalso(bruto=BRUTO)).tempos
    assert set(tempos) == {"imagem", "extrator", "normalizador", "enriquecedor", "validador", "total"}
    assert tempos["total"] >= 0


def test_sem_enriquecimento(foto_png):
    llm = LLMFalso(bruto=BRUTO)
    cardapio = processar(foto_png, cliente=llm, enriquecer_itens=False)
    assert "enriquecedor" not in cardapio.tempos
    assert len(llm.chamadas) == 1
    assert cardapio.enriquecido is False


def test_falha_no_enriquecedor_nao_derruba_o_resultado(foto_png):
    cardapio = processar(foto_png, cliente=LLMFalso(bruto=BRUTO, falhar_enriquecedor=True))
    assert len(cardapio.itens) == 3
    assert cardapio.enriquecido is False


def test_falha_no_extrator_sobe_como_erro(foto_png):
    with pytest.raises(ErroLLM):
        processar(foto_png, cliente=LLMFalso(falhar_extrator=True))


def test_foto_que_nao_e_cardapio_vai_para_revisao(foto_png):
    cardapio = processar(foto_png, cliente=LLMFalso(bruto={"estabelecimento": None, "itens": []}))
    assert [p.tipo for p in cardapio.problemas] == ["cardapio_vazio"]
