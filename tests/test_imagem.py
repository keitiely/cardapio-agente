from io import BytesIO

import pytest
from PIL import Image

from pipeline.imagem import LADO_MAXIMO, preparar_imagem


def _abrir(dados: bytes) -> Image.Image:
    return Image.open(BytesIO(dados))


def test_png_com_transparencia_vira_jpeg_reduzido(foto_png):
    imagem = _abrir(preparar_imagem(foto_png))
    assert imagem.format == "JPEG"
    assert imagem.mode == "RGB"
    assert max(imagem.size) == LADO_MAXIMO


def test_proporcao_e_mantida(foto_png):
    largura, altura = _abrir(preparar_imagem(foto_png)).size
    assert abs(largura / altura - 1.5) < 0.01


def test_imagem_pequena_nao_e_ampliada():
    buffer = BytesIO()
    Image.new("RGB", (400, 300), "white").save(buffer, format="JPEG")
    assert _abrir(preparar_imagem(buffer.getvalue())).size == (400, 300)


def test_rotacao_do_celular_e_aplicada():
    # Foto "deitada" com a etiqueta EXIF que manda girar 90 graus.
    buffer = BytesIO()
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.new("RGB", (400, 200), "white").save(buffer, format="JPEG", exif=exif)
    assert _abrir(preparar_imagem(buffer.getvalue())).size == (200, 400)


def test_arquivo_que_nao_e_imagem_da_erro_claro():
    with pytest.raises(ValueError, match="JPEG, PNG ou WebP"):
        preparar_imagem(b"isto nao e uma imagem")
