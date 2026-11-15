"""Etapa 2 · Normalizador (código, sem IA).

Transforma o texto copiado da foto em dados limpos:
- preço "R$ 25,9" -> 25.9 (número); vários preços ou ilegível -> None
- nome e categoria em CAIXA ALTA -> "Primeira Letra Maiúscula"
- categoria vazia -> "Outros"
- item repetido com o mesmo preço -> fica um só
"""

import re
import unicodedata

from pipeline.schemas import Cardapio, CardapioBruto, Item

# "1.200,00" | "1.200" | "25,90" | "25.90" | "25"
_NUMERO = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?")
_MILHAR_SEM_CENTAVOS = re.compile(r"^\d{1,3}(?:\.\d{3})+$")

# Numeração na frente do nome: "01 - Fritas", "3) Pudim", "12. Água"
_NUMERACAO = re.compile(r"^\s*\d{1,3}\s*[-–—.)]\s+")

_PALAVRAS_MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "com", "sem", "ao", "à", "a", "o", "na", "no", "em"}


def chave_nome(nome: str) -> str:
    """Forma de comparar nomes ignorando acento, maiúscula e espaços extras."""
    sem_acento = unicodedata.normalize("NFKD", nome)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())


def normalizar_preco(texto: str | None) -> float | None:
    """Converte o preço escrito em número. Devolve None se não houver exatamente um preço."""
    if not texto:
        return None
    numeros = _NUMERO.findall(texto)
    if len(numeros) != 1:
        return None  # nenhum preço, ou vários (P/M/G): vai para revisão humana
    numero = numeros[0]
    if "," in numero:
        numero = numero.replace(".", "").replace(",", ".")
    elif _MILHAR_SEM_CENTAVOS.match(numero):
        numero = numero.replace(".", "")
    return round(float(numero), 2)


def normalizar_texto(texto: str | None) -> str:
    """Tira espaços e pontilhados das pontas e ajusta textos em CAIXA ALTA."""
    if not texto:
        return ""
    limpo = " ".join(texto.split()).strip(" .-–—:_·*")
    if limpo.isupper():
        palavras = limpo.lower().split(" ")
        limpo = " ".join(
            p if (i > 0 and p in _PALAVRAS_MINUSCULAS) else _maiuscula(p)
            for i, p in enumerate(palavras)
        )
    return limpo


def _maiuscula(palavra: str) -> str:
    """'x-burguer' -> 'X-Burguer'."""
    return "-".join(parte[:1].upper() + parte[1:] for parte in palavra.split("-"))


def normalizar(bruto: CardapioBruto) -> Cardapio:
    itens: list[Item] = []
    vistos: set[tuple[str, float | None]] = set()

    for item_bruto in bruto.itens:
        nome = normalizar_texto(_NUMERACAO.sub("", item_bruto.nome or ""))
        if not nome:
            continue
        preco = normalizar_preco(item_bruto.preco_texto)
        chave = (chave_nome(nome), preco)
        if chave in vistos:
            continue  # o mesmo item copiado duas vezes
        vistos.add(chave)

        descricao = normalizar_texto(item_bruto.descricao) or None
        itens.append(Item(
            nome=nome,
            preco=preco,
            preco_original=(item_bruto.preco_texto or "").strip() or None,
            categoria=normalizar_texto(item_bruto.categoria) or "Outros",
            descricao=descricao,
        ))

    estabelecimento = normalizar_texto(bruto.estabelecimento) or None
    return Cardapio(estabelecimento=estabelecimento, itens=itens)
