from evals.metricas import avaliar, parear, similaridade
from pipeline.schemas import Cardapio, Item


def _saida(*itens: tuple[str, float | None, str]) -> Cardapio:
    return Cardapio(estabelecimento=None, itens=[Item(nome=n, preco=p, categoria=c) for n, p, c in itens])


def test_similaridade_ignora_acento_e_maiuscula():
    assert similaridade("Água com Gás", "agua com gas") == 1.0


def test_pareia_nomes_com_pequeno_erro_de_leitura():
    assert parear(["Brigadeiro de colher"], ["Brigadeiro de coIher"]) == [(0, 0)]


def test_nao_pareia_nomes_diferentes():
    assert parear(["Pudim"], ["Picanha"]) == []


def test_pareamento_e_um_para_um():
    assert len(parear(["Coxinha", "Coxinha"], ["Coxinha"])) == 1


def test_tudo_certo():
    gabarito = {"itens": [
        {"nome": "Fritas", "preco": 25.90, "categoria": "Entradas"},
        {"nome": "Pizza", "preco": None, "categoria": "Pizzas"},
    ]}
    m = avaliar(gabarito, _saida(("Fritas", 25.9, "Entradas"), ("Pizza", None, "Pizzas")))
    assert (m["cobertura"], m["precisao"], m["preco_certo"], m["categoria_certa"]) == (1.0, 1.0, 1.0, 1.0)


def test_item_faltando_e_item_sobrando():
    gabarito = {"itens": [
        {"nome": "Fritas", "preco": 25.90, "categoria": "Entradas"},
        {"nome": "Pudim", "preco": 15.90, "categoria": "Sobremesas"},
    ]}
    m = avaliar(gabarito, _saida(("Fritas", 25.9, "Entradas"), ("Telefone", 12.0, "Outros")))
    assert m["cobertura"] == 0.5
    assert m["precisao"] == 0.5
    assert m["faltaram"] == ["Pudim"]
    assert m["sobraram"] == ["Telefone"]


def test_preco_e_categoria_errados():
    gabarito = {"itens": [{"nome": "Fritas", "preco": 25.90, "categoria": "Entradas"}]}
    m = avaliar(gabarito, _saida(("Fritas", 29.9, "Porções")))
    assert m["cobertura"] == 1.0
    assert m["preco_certo"] == 0.0
    assert m["categoria_certa"] == 0.0


def test_categoria_com_complemento_conta_como_certa():
    m = avaliar({"itens": [{"nome": "Morango", "preco": 12.0, "categoria": "Bolo de Pote"}]},
                _saida(("Morango", 12.0, "Bolo de Pote 200g")))
    assert m["categoria_certa"] == 1.0


def test_categoria_parecida_mas_diferente_conta_como_errada():
    m = avaliar({"itens": [{"nome": "Bolo", "preco": 40.0, "categoria": "Bolos"}]},
                _saida(("Bolo", 40.0, "Bolo de Pote")))
    assert m["categoria_certa"] == 0.0


def test_categoria_ausente_no_gabarito_vale_outros():
    m = avaliar({"itens": [{"nome": "Café", "preco": 5.0}]}, _saida(("Café", 5.0, "Outros")))
    assert m["categoria_certa"] == 1.0
