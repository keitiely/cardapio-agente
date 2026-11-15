from pipeline.schemas import Cardapio, Item, Tag
from pipeline.validador import _reais, validar


def _cardapio(*itens: Item) -> Cardapio:
    return Cardapio(estabelecimento=None, itens=list(itens))


def _tipos(cardapio: Cardapio) -> list[str]:
    return [p.tipo for p in validar(cardapio).problemas]


def test_cardapio_correto_nao_vai_para_revisao():
    resultado = validar(_cardapio(Item(nome="Café", preco=5.0), Item(nome="Pão de queijo", preco=7.5)))
    assert resultado.problemas == []
    assert resultado.revisao_humana is False


def test_cardapio_vazio():
    resultado = validar(_cardapio())
    assert [p.tipo for p in resultado.problemas] == ["cardapio_vazio"]
    assert resultado.revisao_humana is True


def test_preco_ausente_mostra_o_texto_original():
    resultado = validar(_cardapio(Item(nome="Pizza", preco=None, preco_original="P 30 / G 45")))
    assert resultado.problemas[0].tipo == "preco_ausente"
    assert "P 30 / G 45" in resultado.problemas[0].detalhe


def test_preco_ausente_sem_texto():
    resultado = validar(_cardapio(Item(nome="Pizza", preco=None)))
    assert resultado.problemas[0].detalhe == "O item está sem preço na foto."


def test_preco_acima_da_faixa():
    assert _tipos(_cardapio(Item(nome="Rodízio", preco=1200.0))) == ["preco_fora_da_faixa"]


def test_preco_abaixo_da_faixa():
    assert _tipos(_cardapio(Item(nome="Bala", preco=0.10))) == ["preco_fora_da_faixa"]


def test_limites_da_faixa_sao_aceitos():
    assert _tipos(_cardapio(Item(nome="Bala", preco=0.50), Item(nome="Banquete", preco=1000.0))) == []


def test_nome_repetido_avisa_uma_vez_so():
    tipos = _tipos(_cardapio(
        Item(nome="Coxinha", preco=6.0), Item(nome="coxinha", preco=8.0), Item(nome="COXINHA", preco=9.0),
    ))
    assert tipos == ["nome_repetido"]


def test_tags_conflitantes():
    item = Item(nome="Suco", preco=8.0, tags=[Tag.BEBIDA_ALCOOLICA, Tag.BEBIDA_SEM_ALCOOL])
    assert _tipos(_cardapio(item)) == ["tags_conflitantes"]


def test_tags_compativeis_nao_geram_problema():
    item = Item(nome="Salada", preco=20.0, tags=[Tag.VEGANO, Tag.VEGETARIANO, Tag.SEM_LACTOSE])
    assert _tipos(_cardapio(item)) == []


def test_reais_no_formato_brasileiro():
    assert _reais(1200) == "R$ 1.200,00"
    assert _reais(0.5) == "R$ 0,50"
