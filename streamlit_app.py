"""Cardápio Agente · interface web (Streamlit).

Rodar localmente:   streamlit run streamlit_app.py
No Streamlit Cloud: a chave fica em Settings → Secrets (GEMINI_API_KEY = "...").

Proteções da cota gratuita:
- exemplos prontos (pasta exemplos/) não gastam nenhuma chamada;
- a mesma foto enviada duas vezes reaproveita o resultado;
- cada visitante pode processar até 5 fotos novas por sessão;
- o app inteiro para em 15 fotos novas por dia (a camada gratuita do Gemini
  dá cerca de 20 chamadas por dia por modelo, e cada foto usa 2).
"""

import hashlib
import json
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from pipeline.llm import ErroLLM, obter_cliente
from pipeline.orquestrador import processar
from pipeline.schemas import Cardapio

RAIZ = Path(__file__).parent
PASTA_EXEMPLOS = RAIZ / "exemplos"
RELATORIO_EVALS = RAIZ / "evals" / "saidas" / "relatorio.json"

LIMITE_POR_VISITANTE = 5
LIMITE_POR_DIA = 15
EXTENSOES_FOTO = (".jpg", ".jpeg", ".png", ".webp")

NOMES_PROBLEMAS = {
    "cardapio_vazio": "Cardápio vazio",
    "preco_ausente": "Preço ausente",
    "preco_fora_da_faixa": "Preço fora da faixa",
    "nome_repetido": "Nome repetido",
    "tags_conflitantes": "Tags conflitantes",
}

st.set_page_config(page_title="Cardápio Agente", page_icon="🍽️", layout="wide")


# ---------------------------------------------------------------- dados

@st.cache_resource
def _memoria_global() -> dict:
    """Compartilhada entre todos os visitantes enquanto o app estiver no ar."""
    return {"resultados": {}, "dia": date.today(), "usos_hoje": 0}


def carregar_exemplos() -> dict[str, tuple[Path, Cardapio]]:
    """Cada exemplo é um par: foto (exemplos/nome.jpg) + saída pronta (exemplos/nome.json)."""
    exemplos = {}
    for saida in sorted(PASTA_EXEMPLOS.glob("*.json")):
        fotos = [saida.with_suffix(ext) for ext in EXTENSOES_FOTO if saida.with_suffix(ext).exists()]
        if fotos:
            nome = saida.stem.replace("_", " ").replace("-", " ").title()
            exemplos[nome] = (fotos[0], Cardapio.model_validate_json(saida.read_text(encoding="utf-8")))
    return exemplos


def processar_foto(foto: bytes) -> tuple[Cardapio, str]:
    """Roda o pipeline respeitando os limites. Devolve (cardápio, modelo usado)."""
    memoria = _memoria_global()
    chave = hashlib.sha256(foto).hexdigest()
    if chave in memoria["resultados"]:
        return memoria["resultados"][chave]

    if memoria["dia"] != date.today():
        memoria.update(dia=date.today(), usos_hoje=0)
    if st.session_state.usos >= LIMITE_POR_VISITANTE:
        raise LimiteAtingido(
            f"Você já processou {LIMITE_POR_VISITANTE} fotos nesta sessão. "
            "Use os exemplos prontos ou volte mais tarde."
        )
    if memoria["usos_hoje"] >= LIMITE_POR_DIA:
        raise LimiteAtingido("O limite diário da demo foi atingido. Os exemplos prontos continuam disponíveis.")

    cliente = obter_cliente()
    cardapio = processar(foto, cliente=cliente)
    st.session_state.usos += 1
    memoria["usos_hoje"] += 1
    memoria["resultados"][chave] = (cardapio, cliente.modelo)
    return cardapio, cliente.modelo


class LimiteAtingido(Exception):
    pass


# ---------------------------------------------------------------- exibição

def _reais(valor: float | None) -> str:
    if valor is None:
        return "—"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tabela_itens(cardapio: Cardapio) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Item": i.nome,
            "Preço": _reais(i.preco),
            "Categoria": i.categoria,
            "Descrição": i.descricao or "",
            "Tags": ", ".join(t.value.replace("_", " ") for t in i.tags),
        }
        for i in cardapio.itens
    ])


def mostrar_resultado(cardapio: Cardapio, foto, modelo: str | None = None, de_exemplo: bool = False):
    col_foto, col_dados = st.columns([2, 3], gap="large")

    with col_foto:
        st.image(foto, width="stretch")

    with col_dados:
        if cardapio.estabelecimento:
            st.subheader(cardapio.estabelecimento)

        a, b, c = st.columns(3)
        a.metric("Itens", len(cardapio.itens))
        b.metric("Problemas", len(cardapio.problemas))
        c.metric("Tempo", f"{cardapio.tempos.get('total', 0):.1f} s")

        if cardapio.revisao_humana:
            st.warning("**Precisa de revisão humana** antes de publicar.", icon="🔎")
            for p in cardapio.problemas:
                rotulo = NOMES_PROBLEMAS.get(p.tipo, p.tipo)
                alvo = f" · **{p.item}**" if p.item else ""
                st.markdown(f"- {rotulo}{alvo}: {p.detalhe}")
        else:
            st.success("Nenhum problema encontrado: pronto para publicar.", icon="✅")

        if not cardapio.enriquecido and cardapio.itens:
            st.info("O Enriquecedor não rodou: o cardápio saiu sem tags e sem descrições sugeridas.", icon="ℹ️")

        legenda = "Resultado salvo (não gastou cota)." if de_exemplo else f"Modelo: {modelo}."
        st.caption(legenda)

    st.dataframe(tabela_itens(cardapio), width="stretch", hide_index=True)

    with st.expander("Tempo por etapa"):
        st.bar_chart(
            pd.Series({k: v for k, v in cardapio.tempos.items() if k != "total"}, name="segundos"),
            horizontal=True,
        )

    st.download_button(
        "Baixar JSON",
        data=cardapio.model_dump_json(indent=2),
        file_name="cardapio.json",
        mime="application/json",
    )


# ---------------------------------------------------------------- abas

def aba_demo():
    st.markdown("Envie a foto de um cardápio e veja o JSON estruturado, com os pontos que precisam de revisão humana.")

    exemplos = carregar_exemplos()
    opcoes = ["Enviar minha foto"] + list(exemplos)
    # Abre num exemplo pronto: o visitante vê um resultado na hora, sem gastar cota.
    escolha = st.radio("Origem", opcoes, index=1 if exemplos else 0, horizontal=True, label_visibility="collapsed")

    if escolha != "Enviar minha foto":
        foto, cardapio = exemplos[escolha]
        mostrar_resultado(cardapio, str(foto), de_exemplo=True)
        return

    restantes = LIMITE_POR_VISITANTE - st.session_state.usos
    st.caption(
        f"Você ainda pode processar {restantes} foto(s) nesta sessão. "
        "Envie só fotos de cardápio: a camada gratuita do Gemini pode usar as imagens enviadas."
    )
    arquivo = st.file_uploader("Foto do cardápio (JPEG, PNG ou WebP)", type=["jpg", "jpeg", "png", "webp"])
    if arquivo is None:
        return

    foto = arquivo.getvalue()
    try:
        with st.spinner("Lendo o cardápio… (costuma levar de 10 a 20 segundos)"):
            cardapio, modelo = processar_foto(foto)
    except LimiteAtingido as erro:
        st.warning(str(erro))
        return
    except ValueError as erro:  # arquivo que não é imagem
        st.error(str(erro))
        return
    except ErroLLM as erro:
        st.error("Não consegui ler o cardápio agora. Tente de novo em alguns instantes.")
        with st.expander("Detalhe técnico"):
            st.code(str(erro))
        return
    mostrar_resultado(cardapio, foto, modelo=modelo)


def aba_resultados():
    if not RELATORIO_EVALS.exists():
        st.info("Os evals ainda não foram rodados. Rode `python -m evals.rodar_evals` para gerar este painel.")
        return

    relatorio = json.loads(RELATORIO_EVALS.read_text(encoding="utf-8"))
    st.markdown(
        f"Avaliação em **{relatorio.get('n_cardapios', '?')} cardápios** rotulados à mão, "
        f"com o modelo `{relatorio.get('modelo', '?')}`."
    )
    medias = relatorio.get("medias", {})
    if medias:
        colunas = st.columns(len(medias))
        for coluna, (nome, valor) in zip(colunas, medias.items()):
            coluna.metric(nome, f"{valor:.0%}" if isinstance(valor, float) and valor <= 1 else valor)
    if relatorio.get("por_cardapio"):
        st.dataframe(pd.DataFrame(relatorio["por_cardapio"]), width="stretch", hide_index=True)
    if relatorio.get("nota_tempo_manual"):
        st.caption(relatorio["nota_tempo_manual"])


def aba_como_funciona():
    st.markdown(
        "Um **workflow** de 4 etapas, não um agente autônomo: cada etapa tem uma tarefa só, "
        "e o código, não a IA, decide o que é aceito."
    )
    st.graphviz_chart("""
        digraph {
            rankdir=LR; node [shape=box, style="rounded,filled", fontname="Helvetica", fillcolor="#f4f4f5"];
            foto [label="Foto", shape=note];
            ext [label="1. Extrator\\nLLM com visão\\ncopia sem interpretar", fillcolor="#fde7e9"];
            nor [label="2. Normalizador\\ncódigo\\npreço, nomes, duplicados"];
            enr [label="3. Enriquecedor\\nLLM só texto\\ndescrição + tags", fillcolor="#fde7e9"];
            val [label="4. Validador\\ncódigo\\nregras de negócio"];
            json [label="JSON +\\nrevisão humana", shape=note];
            foto -> ext -> nor -> enr -> val -> json;
            enr -> val [style=dashed, label="se falhar,\\nsegue sem tags", fontsize=10];
        }
    """)
    st.markdown("""
| Etapa | Por que assim |
|---|---|
| **Extrator** | Só copia o texto da foto. Interpretar aqui misturaria dois erros num só e esconderia de onde veio cada um. |
| **Normalizador** | Converter "R$ 1.200,00" em número é regra fixa: código é mais barato, rápido e previsível que IA. |
| **Enriquecedor** | Tags só de uma lista fechada; o Pydantic recusa qualquer tag inventada. É opcional: se falhar, o cardápio sai sem tags. |
| **Validador** | Não tenta consertar: aponta o que um humano precisa olhar (preço ilegível, P/M/G, valores fora da faixa, tags que se contradizem). |

**Provedores:** Gemini (padrão, camada gratuita) ou Claude, trocando só a variável `PROVEDOR`.
Se o modelo principal estiver lotado, o código tenta um modelo reserva.

**Qualidade:** testes automáticos sem chamar a API rodam a cada push, e os evals medem o resultado em cardápios rotulados à mão (aba *Resultados*).
""")


# ---------------------------------------------------------------- página

st.session_state.setdefault("usos", 0)

st.title("🍽️ Cardápio Agente")
st.caption("Foto do cardápio → JSON estruturado, pronto para revisar e publicar.")

demo, resultados, como = st.tabs(["Demo", "Resultados", "Como funciona"])
with demo:
    aba_demo()
with resultados:
    aba_resultados()
with como:
    aba_como_funciona()
