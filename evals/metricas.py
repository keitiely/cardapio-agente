"""Compara a saída do pipeline com o gabarito digitado à mão.

Os itens são pareados pelo nome (ignorando acento, maiúscula e espaços), com
tolerância a pequenas diferenças de leitura: similaridade >= 0,8.
Depois, para cada par, confere se o preço e a categoria batem.

Métricas de um cardápio:
- cobertura: dos itens do gabarito, quantos o sistema encontrou
- precisao: dos itens que o sistema devolveu, quantos existem no gabarito
- preco_certo: entre os pares, quantos têm o preço exato (null com null conta como certo)
- categoria_certa: entre os pares, quantos têm a mesma categoria (aceita complemento
  no fim do título da seção, como peso ou unidade: 'Bolo de Pote' = 'Bolo de Pote 200g')
"""

from difflib import SequenceMatcher

from pipeline.normalizador import chave_nome
from pipeline.schemas import Cardapio

SIMILARIDADE_MINIMA = 0.8


def similaridade(a: str, b: str) -> float:
    return SequenceMatcher(None, chave_nome(a), chave_nome(b)).ratio()


def parear(nomes_gabarito: list[str], nomes_saida: list[str]) -> list[tuple[int, int]]:
    """Pares (índice no gabarito, índice na saída), um para um, dos mais parecidos para os menos."""
    candidatos = sorted(
        (
            (similaridade(g, s), i, j)
            for i, g in enumerate(nomes_gabarito)
            for j, s in enumerate(nomes_saida)
        ),
        reverse=True,
    )
    usados_g: set[int] = set()
    usados_s: set[int] = set()
    pares = []
    for nota, i, j in candidatos:
        if nota < SIMILARIDADE_MINIMA:
            break
        if i in usados_g or j in usados_s:
            continue
        usados_g.add(i)
        usados_s.add(j)
        pares.append((i, j))
    return sorted(pares)


def mesma_categoria(esperada: str, obtida: str) -> bool:
    """Mesma seção, aceitando complemento no fim do título: 'Bolo de Pote' = 'Bolo de Pote 200g'."""
    a, b = chave_nome(esperada), chave_nome(obtida)
    return a == b or b.startswith(a + " ") or a.startswith(b + " ")


def _fracao(parte: int, total: int) -> float:
    return round(parte / total, 3) if total else 1.0


def avaliar(gabarito: dict, saida: Cardapio) -> dict:
    """Métricas de um cardápio. `gabarito` é o JSON digitado à mão."""
    itens_g = gabarito.get("itens", [])
    itens_s = saida.itens
    pares = parear([g["nome"] for g in itens_g], [s.nome for s in itens_s])

    precos_certos = 0
    categorias_certas = 0
    for i, j in pares:
        esperado, obtido = itens_g[i].get("preco"), itens_s[j].preco
        if (esperado is None and obtido is None) or (
            esperado is not None and obtido is not None and abs(esperado - obtido) < 0.005
        ):
            precos_certos += 1
        if mesma_categoria(itens_g[i].get("categoria") or "Outros", itens_s[j].categoria):
            categorias_certas += 1

    return {
        "itens_gabarito": len(itens_g),
        "itens_saida": len(itens_s),
        "pareados": len(pares),
        "cobertura": _fracao(len(pares), len(itens_g)),
        "precisao": _fracao(len(pares), len(itens_s)),
        "preco_certo": _fracao(precos_certos, len(pares)),
        "categoria_certa": _fracao(categorias_certas, len(pares)),
        "faltaram": [itens_g[i]["nome"] for i in range(len(itens_g)) if i not in {p[0] for p in pares}],
        "sobraram": [itens_s[j].nome for j in range(len(itens_s)) if j not in {p[1] for p in pares}],
    }
