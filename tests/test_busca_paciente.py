"""Busca de pacientes por nome, CPF e data de nascimento.

A recepção digita a data de jeitos diferentes — com barra, com traço, sem
nada — e a busca precisa entender todos eles.
"""

from datetime import date

import pytest
from conftest import SENHA_ADMIN, fazer_login
from models import Patient, User, db


def semear(app):
    with app.app_context():
        admin = db.session.scalar(
            db.select(User).where(User.email == "admin@teste.com")
        )
        db.session.add_all(
            [
                Patient(
                    nome="Josue Silva",
                    cpf="11157639873",
                    data_nascimento=date(1983, 10, 1),
                    fisioterapeuta_id=admin.id,
                    ativo=True,
                ),
                Patient(
                    nome="Marta Ribeiro",
                    cpf="52998224725",
                    data_nascimento=date(1975, 3, 22),
                    fisioterapeuta_id=admin.id,
                    ativo=True,
                ),
                Patient(
                    nome="Sem Nascimento",
                    fisioterapeuta_id=admin.id,
                    ativo=True,
                ),
            ]
        )
        db.session.commit()


def buscar(client, texto):
    return client.get(f"/pacientes?q={texto}").get_data(as_text=True)


@pytest.mark.parametrize(
    "texto",
    ["01/10/1983", "01-10-1983", "1983-10-01", "01.10.1983", "01101983"],
)
def test_encontra_pelo_nascimento_em_varios_formatos(client, app, texto):
    semear(app)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    pagina = buscar(client, texto)

    assert "Josue Silva" in pagina
    assert "Marta Ribeiro" not in pagina


def test_continua_encontrando_pelo_nome(client, app):
    semear(app)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    pagina = buscar(client, "Marta")

    assert "Marta Ribeiro" in pagina
    assert "Josue Silva" not in pagina


def test_continua_encontrando_pelo_cpf(client, app):
    semear(app)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    pagina = buscar(client, "111.576.398-73")

    assert "Josue Silva" in pagina
    assert "Marta Ribeiro" not in pagina


def test_data_que_nao_existe_no_calendario_nao_quebra(client, app):
    """31/02 não é data: a busca tem que cair de volta em nome e CPF."""
    semear(app)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    resposta = client.get("/pacientes?q=31/02/1990")

    assert resposta.status_code == 200
    assert "Josue Silva" not in resposta.get_data(as_text=True)


def test_texto_qualquer_nao_vira_data(client, app):
    semear(app)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    pagina = buscar(client, "Sem")

    assert "Sem Nascimento" in pagina
