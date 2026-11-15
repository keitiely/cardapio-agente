import pytest

from pipeline.normalizador import chave_nome, normalizar, normalizar_preco, normalizar_texto
from pipeline.schemas import CardapioBruto


@pytest.mark.parametrize("texto, esperado", [
    ("R$ 25,90", 25.90),
    ("R$25,9", 25.90),
    ("25.90", 25.90),
    ("R$ 20", 20.0),
    ("1.200", 1200.0),
    ("R$ 1.200,00", 1200.0),
    ("12,5", 12.5),
])
def test_preco_unico_vira_numero(texto, esperado):
    assert normalizar_preco(texto) == esperado


@pytest.mark.parametrize("texto", [
    None,
    "",
    "consulte",
    "P 30,00 / G 45,00",          # vários tamanhos: vai para revisão humana
    "P 30 M 38 G 45",
])
def test_preco_ausente_ou_multiplo_vira_none(texto):
    assert normalizar_preco(texto) is None


@pytest.mark.parametrize("texto, esperado", [
    ("X-BURGUER", "X-Burguer"),
    ("PASTEL DE CARNE COM QUEIJO", "Pastel de Carne com Queijo"),
    ("Suco de Laranja ....", "Suco de Laranja"),
    ("  Pudim   de  leite ", "Pudim de leite"),   # só mexe na caixa se estiver TODO em maiúsculas
    ("COCA-COLA 350ML", "Coca-Cola 350ml"),
    ("A FEIJOADA", "A Feijoada"),          # palavra pequena no começo fica maiúscula
])
def test_normalizar_texto(texto, esperado):
    assert normalizar_texto(texto) == esperado


def test_chave_nome_ignora_acento_maiuscula_e_espacos():
    assert chave_nome("  Água  com GÁS ") == chave_nome("agua com gas")


def _bruto(itens, estabelecimento=None):
    return CardapioBruto.model_validate({"estabelecimento": estabelecimento, "itens": itens})


def test_normalizar_remove_numeracao_do_nome():
    cardapio = normalizar(_bruto([
        {"nome": "01 - Fritas", "preco_texto": "25,90"},
        {"nome": "3) Pudim", "preco_texto": "15,90"},
        {"nome": "12. Água", "preco_texto": "3,90"},
    ]))
    assert [i.nome for i in cardapio.itens] == ["Fritas", "Pudim", "Água"]


def test_normalizar_mantem_numero_que_faz_parte_do_nome():
    cardapio = normalizar(_bruto([{"nome": "7 Belo", "preco_texto": "5"}]))
    assert cardapio.itens[0].nome == "7 Belo"


def test_item_repetido_com_mesmo_preco_fica_um_so():
    cardapio = normalizar(_bruto([
        {"nome": "X-BURGUER", "preco_texto": "R$ 25,9"},
        {"nome": "X-Burguer", "preco_texto": "25,90"},
    ]))
    assert len(cardapio.itens) == 1


def test_mesmo_nome_com_preco_diferente_fica_nos_dois():
    cardapio = normalizar(_bruto([
        {"nome": "Coxinha", "preco_texto": "6,00"},
        {"nome": "Coxinha", "preco_texto": "8,00"},
    ]))
    assert len(cardapio.itens) == 2


def test_item_sem_nome_e_descartado():
    cardapio = normalizar(_bruto([{"nome": "  ", "preco_texto": "10"}, {"nome": "Café", "preco_texto": "5"}]))
    assert [i.nome for i in cardapio.itens] == ["Café"]


def test_categoria_vazia_vira_outros_e_preco_original_e_guardado():
    item = normalizar(_bruto([{"nome": "Pizza", "preco_texto": " P 30 / G 45 "}])).itens[0]
    assert item.categoria == "Outros"
    assert item.preco is None
    assert item.preco_original == "P 30 / G 45"


def test_estabelecimento_e_normalizado():
    assert normalizar(_bruto([], "LANCHONETE DO ZÉ")).estabelecimento == "Lanchonete do Zé"
