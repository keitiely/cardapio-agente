from conftest import LLMFalso

from pipeline import enriquecedor
from pipeline.enriquecedor import enriquecer
from pipeline.schemas import Cardapio, Item, Tag


def _cardapio(*nomes: str, descricao: str | None = None) -> Cardapio:
    return Cardapio(estabelecimento=None, itens=[Item(nome=n, preco=10.0, descricao=descricao) for n in nomes])


def test_adiciona_descricao_e_tags():
    llm = LLMFalso(enriquecimento={"itens": [
        {"nome": "Fritas", "descricao": "Porção de batata frita.", "tags": ["frito", "para_compartilhar"]},
    ]})
    resultado = enriquecer(_cardapio("Fritas"), llm)
    item = resultado.itens[0]
    assert item.descricao == "Porção de batata frita."
    assert item.tags == [Tag.FRITO, Tag.PARA_COMPARTILHAR]
    assert resultado.enriquecido is True


def test_mantem_descricao_original_da_foto():
    llm = LLMFalso(enriquecimento={"itens": [{"nome": "Pudim", "descricao": "Inventada", "tags": ["doce"]}]})
    item = enriquecer(_cardapio("Pudim", descricao="Sem furinhos, tá?"), llm).itens[0]
    assert item.descricao == "Sem furinhos, tá?"
    assert item.tags == [Tag.DOCE]


def test_casa_nome_mesmo_com_acento_e_maiuscula_diferentes():
    llm = LLMFalso(enriquecimento={"itens": [{"nome": "agua com gas", "descricao": "Água.", "tags": ["bebida_sem_alcool"]}]})
    assert enriquecer(_cardapio("Água com Gás"), llm).itens[0].tags == [Tag.BEBIDA_SEM_ALCOOL]


def test_tags_repetidas_viram_uma_so():
    llm = LLMFalso(enriquecimento={"itens": [{"nome": "Pudim", "descricao": "Pudim.", "tags": ["doce", "doce"]}]})
    assert enriquecer(_cardapio("Pudim"), llm).itens[0].tags == [Tag.DOCE]


def test_descricao_sugerida_e_cortada_em_140():
    llm = LLMFalso(enriquecimento={"itens": [{"nome": "Prato", "descricao": "x" * 300, "tags": []}]})
    assert len(enriquecer(_cardapio("Prato"), llm).itens[0].descricao) == 140


def test_item_sem_sugestao_fica_como_estava():
    resultado = enriquecer(_cardapio("Fritas", "Pudim"), LLMFalso(enriquecimento={"itens": []}))
    assert all(i.tags == [] and i.descricao is None for i in resultado.itens)


def test_falha_do_llm_devolve_cardapio_sem_tags():
    cardapio = _cardapio("Fritas")
    resultado = enriquecer(cardapio, LLMFalso(falhar_enriquecedor=True))
    assert resultado.enriquecido is False
    assert resultado.itens == cardapio.itens


def test_cardapio_vazio_nao_chama_o_llm():
    llm = LLMFalso()
    enriquecer(_cardapio(), llm)
    assert llm.chamadas == []


def test_itens_vao_em_lotes(monkeypatch):
    monkeypatch.setattr(enriquecedor, "TAMANHO_LOTE", 2)
    llm = LLMFalso()
    enriquecer(_cardapio("A", "B", "C", "D", "E"), llm)
    assert len(llm.chamadas) == 3  # 2 + 2 + 1


def test_enriquecedor_nao_manda_imagem():
    llm = LLMFalso()
    enriquecer(_cardapio("Fritas"), llm)
    assert llm.chamadas == [("EnriquecimentoLote", False)]
