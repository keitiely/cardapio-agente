"""Roda o pipeline nos cardápios de evals/fotos e compara com evals/gabaritos.

Uso (na raiz do projeto, com a .venv ativa):
    python -m evals.rodar_evals            # reaproveita saídas já salvas
    python -m evals.rodar_evals --refazer  # chama a API de novo para todas as fotos

Cada foto só é processada se tiver um gabarito com o mesmo nome.
As saídas ficam em evals/saidas/<nome>.json, para não gastar cota toda vez,
e o resumo vai para evals/saidas/relatorio.json (lido pela aba Resultados do app).
"""

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

from evals.metricas import avaliar
from pipeline.llm import ErroLLM, obter_cliente
from pipeline.orquestrador import processar
from pipeline.schemas import Cardapio

PASTA = Path(__file__).parent
FOTOS = PASTA / "fotos"
GABARITOS = PASTA / "gabaritos"
SAIDAS = PASTA / "saidas"
RELATORIO = SAIDAS / "relatorio.json"
EXTENSOES = (".jpg", ".jpeg", ".png", ".webp")


def casos() -> list[tuple[str, Path, Path]]:
    """(nome, foto, gabarito) para cada foto que tem gabarito."""
    resultado = []
    for foto in sorted(FOTOS.iterdir()):
        if foto.suffix.lower() not in EXTENSOES:
            continue
        gabarito = GABARITOS / f"{foto.stem}.json"
        if gabarito.exists():
            resultado.append((foto.stem, foto, gabarito))
        else:
            print(f"  (sem gabarito, pulando) {foto.name}")
    return resultado


def obter_saida(nome: str, foto: Path, refazer: bool, cliente) -> tuple[Cardapio, str]:
    arquivo = SAIDAS / f"{nome}.json"
    if arquivo.exists() and not refazer:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        return Cardapio.model_validate(dados["cardapio"]), dados["modelo"]
    cardapio = processar(foto.read_bytes(), cliente=cliente)
    arquivo.write_text(
        json.dumps({"modelo": cliente.modelo, "cardapio": cardapio.model_dump(mode="json")}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return cardapio, cliente.modelo


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refazer", action="store_true", help="ignora as saídas salvas e chama a API de novo")
    args = parser.parse_args()

    SAIDAS.mkdir(exist_ok=True)
    lista = casos()
    if not lista:
        print("Nenhum caso: coloque fotos em evals/fotos/ e gabaritos com o mesmo nome em evals/gabaritos/.")
        return 1

    cliente = None
    linhas = []
    modelos = set()
    for nome, foto, arq_gabarito in lista:
        print(f"→ {nome}")
        precisa_api = args.refazer or not (SAIDAS / f"{nome}.json").exists()
        if precisa_api and cliente is None:
            cliente = obter_cliente()
        try:
            saida, modelo = obter_saida(nome, foto, args.refazer, cliente)
        except ErroLLM as erro:
            print(f"  ERRO: {erro}")
            continue
        modelos.add(modelo)

        gabarito = json.loads(arq_gabarito.read_text(encoding="utf-8"))
        m = avaliar(gabarito, saida)
        linhas.append({
            "Cardápio": nome,
            "Itens (gabarito)": m["itens_gabarito"],
            "Cobertura": m["cobertura"],
            "Precisão": m["precisao"],
            "Preço certo": m["preco_certo"],
            "Categoria certa": m["categoria_certa"],
            "Revisão humana": "sim" if saida.revisao_humana else "não",
            "Tempo agente (s)": saida.tempos.get("total"),
            "Tempo manual (min)": gabarito.get("tempo_manual_min"),
            "Faltaram": ", ".join(m["faltaram"]),
            "Sobraram": ", ".join(m["sobraram"]),
        })
        print(f"  cobertura {m['cobertura']:.0%} · precisão {m['precisao']:.0%} · "
              f"preço {m['preco_certo']:.0%} · categoria {m['categoria_certa']:.0%}")

    if not linhas:
        print("Nenhum cardápio avaliado.")
        return 1

    def media(coluna: str) -> float | None:
        valores = [l[coluna] for l in linhas if isinstance(l[coluna], (int, float))]
        return round(mean(valores), 3) if valores else None

    medias = {
        "Cobertura": media("Cobertura"),
        "Precisão": media("Precisão"),
        "Preço certo": media("Preço certo"),
        "Categoria certa": media("Categoria certa"),
        "Tempo agente (s)": media("Tempo agente (s)"),
        "Tempo manual (min)": media("Tempo manual (min)"),
    }
    relatorio = {
        "n_cardapios": len(linhas),
        "modelo": ", ".join(sorted(modelos)),
        "medias": {k: v for k, v in medias.items() if v is not None},
        "por_cardapio": linhas,
    }
    RELATORIO.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nMédias:")
    for nome, valor in relatorio["medias"].items():
        print(f"  {nome}: {valor:.0%}" if valor <= 1 and "Tempo" not in nome else f"  {nome}: {valor}")
    print(f"\nRelatório salvo em {RELATORIO.relative_to(PASTA.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
