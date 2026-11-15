"""Etapa 4 · Validador (código, sem IA).

Regras de negócio que decidem se o cardápio precisa de revisão humana:
- cardápio sem nenhum item
- preço ausente ou ilegível (inclui P/M/G na mesma linha)
- preço fora da faixa de R$ 0,50 a R$ 1.000
- mesmo nome aparecendo mais de uma vez (com preços diferentes)
- tags que se contradizem (ex.: vegano + contém lactose)
"""

from collections import Counter

from pipeline.normalizador import chave_nome
from pipeline.schemas import PRECO_MAXIMO, PRECO_MINIMO, TAGS_CONFLITANTES, Cardapio, Problema


def _reais(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def validar(cardapio: Cardapio) -> Cardapio:
    problemas: list[Problema] = []

    if not cardapio.itens:
        problemas.append(Problema(item="", tipo="cardapio_vazio", detalhe="Nenhum item foi encontrado na foto."))

    contagem = Counter(chave_nome(i.nome) for i in cardapio.itens)
    repetidos_avisados: set[str] = set()

    for item in cardapio.itens:
        if item.preco is None:
            detalhe = (
                f"Não deu para ler um preço único em '{item.preco_original}'."
                if item.preco_original else "O item está sem preço na foto."
            )
            problemas.append(Problema(item=item.nome, tipo="preco_ausente", detalhe=detalhe))
        elif not PRECO_MINIMO <= item.preco <= PRECO_MAXIMO:
            problemas.append(Problema(
                item=item.nome,
                tipo="preco_fora_da_faixa",
                detalhe=f"{_reais(item.preco)} está fora da faixa de {_reais(PRECO_MINIMO)} a {_reais(PRECO_MAXIMO)}.",
            ))

        chave = chave_nome(item.nome)
        if contagem[chave] > 1 and chave not in repetidos_avisados:
            repetidos_avisados.add(chave)
            problemas.append(Problema(
                item=item.nome,
                tipo="nome_repetido",
                detalhe=f"Aparece {contagem[chave]} vezes com preços diferentes.",
            ))

        tags = set(item.tags)
        for a, b in TAGS_CONFLITANTES:
            if a in tags and b in tags:
                problemas.append(Problema(
                    item=item.nome,
                    tipo="tags_conflitantes",
                    detalhe=f"As tags '{a.value}' e '{b.value}' se contradizem.",
                ))

    return cardapio.model_copy(update={"problemas": problemas, "revisao_humana": bool(problemas)})
