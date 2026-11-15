"""Etapa 3 · Enriquecedor (LLM, só texto).

Para cada item, sugere uma descrição curta e tags da lista fechada.
- Se o item já tem descrição na foto, ela é mantida (é o texto real do restaurante).
- Se a chamada falhar, o cardápio segue sem tags: esta etapa é opcional.
- Itens vão em lotes, para gastar poucas chamadas da cota gratuita.
"""

import json
import logging

from pipeline.llm import ClienteLLM, ErroLLM
from pipeline.normalizador import chave_nome
from pipeline.schemas import Cardapio, EnriquecimentoLote, Tag

TAMANHO_LOTE = 40

PROMPT_ENRIQUECEDOR = """Você vai enriquecer itens de um cardápio brasileiro.
Para cada item recebido, devolva:
- nome: igual ao recebido, sem mudar nada.
- descricao: frase curta e neutra, até 100 caracteres, dizendo o que o item é.
  Use só o que está no nome, na categoria e na descrição recebida.
  Proibido: inventar ingredientes, modo de preparo, tamanho ou temperatura, e usar
  adjetivos de propaganda (crocante, suculento, delicioso, refrescante, gelado,
  apetitoso, saboroso, dourado, macio...).
  Exemplos: "Batata Palito" -> "Porção de batata frita em palito."
            "Suco natural" -> "Suco natural de fruta."
- tags: só da lista permitida. Inclua uma tag apenas se ela for óbvia pelo nome ou
  pela descrição (ex.: "frito" para frito, empanado, batata frita, iscas fritas).
  Na dúvida, deixe de fora.

Tags permitidas: {tags}

Itens (JSON):
{itens}
"""


def _prompt(lote: list[dict]) -> str:
    tags = ", ".join(t.value for t in Tag)
    return PROMPT_ENRIQUECEDOR.format(tags=tags, itens=json.dumps(lote, ensure_ascii=False, indent=1))


def enriquecer(cardapio: Cardapio, cliente: ClienteLLM) -> Cardapio:
    if not cardapio.itens:
        return cardapio

    sugestoes: dict[str, tuple[str, list[Tag]]] = {}
    entrada = [
        {"nome": i.nome, "categoria": i.categoria, "descricao": i.descricao}
        for i in cardapio.itens
    ]
    try:
        for inicio in range(0, len(entrada), TAMANHO_LOTE):
            lote = entrada[inicio:inicio + TAMANHO_LOTE]
            resposta = cliente.gerar(_prompt(lote), EnriquecimentoLote)
            for e in resposta.itens:
                sugestoes[chave_nome(e.nome)] = (e.descricao.strip(), list(dict.fromkeys(e.tags)))
    except ErroLLM as erro:
        logging.warning("Enriquecedor pulado, cardápio segue sem tags: %s", erro)
        return cardapio.model_copy(update={"enriquecido": False})

    itens = []
    for item in cardapio.itens:
        sugestao = sugestoes.get(chave_nome(item.nome))
        if sugestao is None:
            itens.append(item)
            continue
        descricao, tags = sugestao
        itens.append(item.model_copy(update={
            "descricao": item.descricao or descricao[:140] or None,
            "tags": tags,
        }))
    return cardapio.model_copy(update={"itens": itens, "enriquecido": True})
