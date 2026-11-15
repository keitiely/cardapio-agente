"""Modelos de dados do pipeline.

Cada etapa recebe e devolve um destes modelos, então este arquivo é o contrato
entre as 4 etapas:

    foto -> Extrator -> CardapioBruto
         -> Normalizador -> Cardapio (itens com preço numérico)
         -> Enriquecedor -> Cardapio (com descrição e tags)
         -> Validador -> Cardapio (com problemas e flag de revisão humana)
"""

from enum import Enum

from pydantic import BaseModel, Field

# Faixa de preço aceita sem revisão humana (em reais).
PRECO_MINIMO = 0.50
PRECO_MAXIMO = 1000.00


class Tag(str, Enum):
    """Lista fechada de tags. O Enriquecedor só pode escolher daqui."""

    VEGETARIANO = "vegetariano"
    VEGANO = "vegano"
    SEM_GLUTEN = "sem_gluten"
    CONTEM_GLUTEN = "contem_gluten"
    SEM_LACTOSE = "sem_lactose"
    CONTEM_LACTOSE = "contem_lactose"
    APIMENTADO = "apimentado"
    DOCE = "doce"
    FRITO = "frito"
    GRELHADO = "grelhado"
    BEBIDA_ALCOOLICA = "bebida_alcoolica"
    BEBIDA_SEM_ALCOOL = "bebida_sem_alcool"
    INDIVIDUAL = "individual"
    PARA_COMPARTILHAR = "para_compartilhar"


# Pares que não podem aparecer juntos no mesmo item. O Validador usa esta lista.
TAGS_CONFLITANTES: list[tuple[Tag, Tag]] = [
    (Tag.VEGANO, Tag.CONTEM_LACTOSE),
    (Tag.SEM_GLUTEN, Tag.CONTEM_GLUTEN),
    (Tag.SEM_LACTOSE, Tag.CONTEM_LACTOSE),
    (Tag.BEBIDA_ALCOOLICA, Tag.BEBIDA_SEM_ALCOOL),
    (Tag.INDIVIDUAL, Tag.PARA_COMPARTILHAR),
]


# ---------- Etapa 1: Extrator (texto copiado da foto, sem interpretar) ----------

class ItemBruto(BaseModel):
    nome: str = Field(description="Nome do item exatamente como está na foto.")
    preco_texto: str | None = Field(
        default=None,
        description="Preço exatamente como escrito, ex.: 'R$ 25,90' ou '25,9'. Nulo se não houver.",
    )
    categoria: str | None = Field(
        default=None,
        description="Título da seção onde o item aparece, ex.: 'Lanches'. Nulo se não houver.",
    )
    descricao: str | None = Field(
        default=None,
        description="Texto descritivo que aparece junto ao item na foto. Nulo se não houver.",
    )


class CardapioBruto(BaseModel):
    estabelecimento: str | None = Field(default=None, description="Nome do restaurante, se aparecer.")
    itens: list[ItemBruto] = Field(default_factory=list)


# ---------- Etapa 3: Enriquecedor (saída do LLM para um item) ----------

class Enriquecimento(BaseModel):
    nome: str = Field(description="Nome do item, igual ao recebido.")
    descricao: str = Field(description="Descrição curta e apetitosa, até 140 caracteres, sem inventar ingredientes.")
    tags: list[Tag] = Field(default_factory=list, description="Só tags que dá para afirmar pelo nome e descrição.")


class EnriquecimentoLote(BaseModel):
    itens: list[Enriquecimento] = Field(default_factory=list)


# ---------- Cardápio final (Normalizador, Enriquecedor e Validador) ----------

class Item(BaseModel):
    nome: str
    preco: float | None = None
    preco_original: str | None = None  # texto da foto, para a revisão humana
    categoria: str = "Outros"
    descricao: str | None = None
    tags: list[Tag] = Field(default_factory=list)


class Problema(BaseModel):
    item: str
    tipo: str  # preco_ausente | preco_fora_da_faixa | nome_repetido | tags_conflitantes
    detalhe: str


class Cardapio(BaseModel):
    estabelecimento: str | None = None
    itens: list[Item] = Field(default_factory=list)
    problemas: list[Problema] = Field(default_factory=list)
    revisao_humana: bool = False
    enriquecido: bool = False
    tempos: dict[str, float] = Field(default_factory=dict)  # segundos por etapa
