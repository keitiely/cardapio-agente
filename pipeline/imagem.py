"""Prepara a foto antes de mandar para o LLM.

Reduzir a foto economiza cota e deixa a chamada mais rápida, sem perder a
leitura do texto: 1568 px no lado maior é suficiente para cardápios.
"""

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

LADO_MAXIMO = 1568


def preparar_imagem(dados: bytes, lado_maximo: int = LADO_MAXIMO, qualidade: int = 85) -> bytes:
    """Corrige a rotação do celular, reduz o lado maior para `lado_maximo` e devolve JPEG."""
    try:
        img = Image.open(BytesIO(dados))
        img = ImageOps.exif_transpose(img)
    except (UnidentifiedImageError, OSError) as erro:
        raise ValueError("O arquivo não é uma imagem que dá para abrir (use JPEG, PNG ou WebP).") from erro

    if img.mode in ("RGBA", "LA", "P"):
        # Fundo branco no lugar da transparência, senão vira preto no JPEG.
        img = img.convert("RGBA")
        fundo = Image.new("RGB", img.size, (255, 255, 255))
        fundo.paste(img, mask=img.getchannel("A"))
        img = fundo
    elif img.mode != "RGB":
        img = img.convert("RGB")

    img.thumbnail((lado_maximo, lado_maximo))

    saida = BytesIO()
    img.save(saida, format="JPEG", quality=qualidade)
    return saida.getvalue()
