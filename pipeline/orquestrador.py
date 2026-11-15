"""Orquestrador: encadeia as 4 etapas e mede o tempo de cada uma.

Uso pelo terminal (primeiro teste real):
    python -m pipeline.orquestrador caminho/da/foto.jpg
"""

import sys
from pathlib import Path
from time import perf_counter

from pipeline.enriquecedor import enriquecer
from pipeline.extrator import extrair
from pipeline.imagem import preparar_imagem
from pipeline.llm import ClienteLLM, obter_cliente
from pipeline.normalizador import normalizar
from pipeline.schemas import Cardapio
from pipeline.validador import validar


def processar(foto: bytes, cliente: ClienteLLM | None = None, enriquecer_itens: bool = True) -> Cardapio:
    """Foto (bytes) -> Cardapio validado. Levanta ErroLLM se o Extrator falhar."""
    cliente = cliente or obter_cliente()
    tempos: dict[str, float] = {}

    def medir(nome: str, inicio: float) -> None:
        tempos[nome] = round(perf_counter() - inicio, 2)

    inicio = perf_counter()
    imagem = preparar_imagem(foto)
    medir("imagem", inicio)

    inicio = perf_counter()
    bruto = extrair(imagem, cliente)
    medir("extrator", inicio)

    inicio = perf_counter()
    cardapio = normalizar(bruto)
    medir("normalizador", inicio)

    if enriquecer_itens:
        inicio = perf_counter()
        cardapio = enriquecer(cardapio, cliente)
        medir("enriquecedor", inicio)

    inicio = perf_counter()
    cardapio = validar(cardapio)
    medir("validador", inicio)

    tempos["total"] = round(sum(tempos.values()), 2)
    return cardapio.model_copy(update={"tempos": tempos})


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python -m pipeline.orquestrador caminho/da/foto.jpg")
    resultado = processar(Path(sys.argv[1]).read_bytes())
    print(resultado.model_dump_json(indent=2))
