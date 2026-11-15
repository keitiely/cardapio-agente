"""Teste de fumaça da interface: o app abre e mostra as 3 abas, sem chamar a API."""

from streamlit.testing.v1 import AppTest


def test_app_abre_sem_erro():
    app = AppTest.from_file("../streamlit_app.py", default_timeout=30).run()
    assert not app.exception
    assert [aba.label for aba in app.tabs] == ["Demo", "Resultados", "Como funciona"]
