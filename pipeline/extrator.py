"""Etapa 1 · Extrator (LLM com visão).

Só copia o texto da foto para o formato CardapioBruto. Não converte preço,
não corrige nome, não inventa nada: interpretar é trabalho do Normalizador,
que é código e tem testes.
"""

from pipeline.llm import ClienteLLM
from pipeline.schemas import CardapioBruto

PROMPT_EXTRATOR = """Você recebe a foto de um cardápio de restaurante brasileiro.
Copie o texto para o formato pedido, sem interpretar.

Regras:
- Um item para cada prato ou bebida.
- nome: exatamente como está escrito (mesmas maiúsculas e acentos).
- preco_texto: exatamente como está escrito, com "R$" se houver.
  Se o item tiver vários tamanhos ou preços (ex.: P/M/G), copie todos no mesmo campo,
  como "P 30,00 / G 45,00".
- categoria: o título da seção onde o item está, como escrito.
- descricao: o texto que descreve o item na foto, se houver.
- estabelecimento: o nome do restaurante, se aparecer.
- Não invente itens, preços nem descrições. Não traduza.
- Ignore o que não é item: endereço, telefone, horário, redes sociais, avisos.
- Se a imagem não for um cardápio, devolva a lista de itens vazia.
"""


def extrair(imagem: bytes, cliente: ClienteLLM) -> CardapioBruto:
    """Recebe a foto já preparada (JPEG reduzido) e devolve o texto estruturado."""
    return cliente.gerar(PROMPT_EXTRATOR, CardapioBruto, imagem=imagem)
