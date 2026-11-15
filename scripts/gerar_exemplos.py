"""Gera os exemplos prontos da demo a partir das saídas salvas dos evals.

Uso (na raiz do projeto):
    python -m scripts.gerar_exemplos                    # salgados, tapiocas e self-service
    python -m scripts.gerar_exemplos caseiro tapiocas   # escolhendo os cardápios

Não chama a API: usa a leitura do LLM já salva em evals/saidas/ e reaplica só as
etapas de código (normalização de textos e validação), que são determinísticas.
Para cada cardápio, copia a foto e grava o resultado em exemplos/<nome>.json.
"""

import json
import shutil
import sys
from pathlib import Path

from pipeline.normalizador import normalizar_texto
from pipeline.schemas import Cardapio
from pipeline.validador import validar

RAIZ = Path(__file__).resolve().parent.parent
FOTOS = RAIZ / "evals" / "fotos"
SAIDAS = RAIZ / "evals" / "saidas"
EXEMPLOS = RAIZ / "exemplos"
PADRAO = ["salgados", "tapiocas", "self-service"]


def gerar(nome: str) -> None:
    saida = SAIDAS / f"{nome}.json"
    fotos = [f for f in FOTOS.glob(f"{nome}.*") if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    if not saida.exists() or not fotos:
        raise SystemExit(f"Faltam a foto ou a saída de '{nome}'. Rode antes: python -m evals.rodar_evals")

    cardapio = Cardapio.model_validate(json.loads(saida.read_text(encoding="utf-8"))["cardapio"])
    itens = [
        item.model_copy(update={"nome": normalizar_texto(item.nome), "categoria": normalizar_texto(item.categoria)})
        for item in cardapio.itens
    ]
    estabelecimento = normalizar_texto(cardapio.estabelecimento) or None
    cardapio = validar(cardapio.model_copy(update={"itens": itens, "estabelecimento": estabelecimento}))

    shutil.copy(fotos[0], EXEMPLOS / fotos[0].name)
    (EXEMPLOS / f"{nome}.json").write_text(cardapio.model_dump_json(indent=2), encoding="utf-8")
    print(f"  {nome}: {len(cardapio.itens)} itens, {len(cardapio.problemas)} problema(s)")


def main() -> None:
    EXEMPLOS.mkdir(exist_ok=True)
    for nome in sys.argv[1:] or PADRAO:
        gerar(nome)
    print(f"Exemplos em {EXEMPLOS.relative_to(RAIZ)}/")


if __name__ == "__main__":
    main()
