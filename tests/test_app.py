"""Teste de fumaça da interface: o app abre e mostra as 3 abas, sem chamar a API."""

from streamlit.testing.v1 import AppTest


def test_app_abre_sem_erro():
    app = AppTest.from_file("../streamlit_app.py", default_timeout=30).run()
    assert not app.exception
    assert [aba.label for aba in app.tabs] == ["Demo", "Resultados", "Como funciona"]


def test_exemplos_prontos_abrem_sem_chamar_a_api():
    app = AppTest.from_file("../streamlit_app.py", default_timeout=30).run()
    opcoes = app.radio[0].options
    assert opcoes[0] == "Enviar minha foto"
    for exemplo in opcoes[1:]:
        app.radio[0].set_value(exemplo).run()
        assert not app.exception, exemplo
        assert any("não gastou cota" in c.value for c in app.caption)
