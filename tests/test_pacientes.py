"""Testes do módulo de pacientes, com foco na regra de acesso por dono."""

from conftest import SENHA_ADMIN, SENHA_FISIO, criar_usuario, fazer_login
from models import PHYSIOTHERAPIST_PROFILE, Patient, db


def criar_paciente(app, nome, fisioterapeuta_id):
    with app.app_context():
        paciente = Patient(nome=nome, fisioterapeuta_id=fisioterapeuta_id, ativo=True)
        db.session.add(paciente)
        db.session.commit()
        return paciente.id


def id_do_usuario(app, email):
    with app.app_context():
        from models import User

        return db.session.scalar(db.select(User).where(User.email == email)).id


def test_listagem_exige_autenticacao(client):
    resposta = client.get("/pacientes")
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_fisioterapeuta_ve_apenas_os_proprios_pacientes(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")

    with app.app_context():
        outro = criar_usuario(
            "Outro Fisio", "outro@teste.com", "Senha@123", PHYSIOTHERAPIST_PROFILE
        )
        db.session.add(outro)
        db.session.commit()
        id_outro = outro.id

    criar_paciente(app, "Paciente Proprio", id_fisio)
    criar_paciente(app, "Paciente Alheio", id_outro)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/pacientes").get_data(as_text=True)

    assert "Paciente Proprio" in corpo
    assert "Paciente Alheio" not in corpo


def test_admin_ve_todos_os_pacientes(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_admin = id_do_usuario(app, "admin@teste.com")

    criar_paciente(app, "Paciente Do Fisio", id_fisio)
    criar_paciente(app, "Paciente Do Admin", id_admin)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    corpo = client.get("/pacientes").get_data(as_text=True)

    assert "Paciente Do Fisio" in corpo
    assert "Paciente Do Admin" in corpo


def test_cadastro_vincula_paciente_a_quem_cadastrou(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    client.post("/pacientes/novo", data={"nome": "Maria Souza"}, follow_redirects=True)

    with app.app_context():
        paciente = db.session.scalar(
            db.select(Patient).where(Patient.nome == "Maria Souza")
        )
        assert paciente is not None
        assert paciente.fisioterapeuta_id == id_fisio


def test_cadastro_sem_nome_e_recusado(client):
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    resposta = client.post("/pacientes/novo", data={"nome": "   "})
    assert resposta.status_code == 400


def test_data_de_nascimento_invalida_nao_derruba_a_pagina(client):
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    resposta = client.post(
        "/pacientes/novo",
        data={"nome": "Joao Teste", "data_nascimento": "31/02/2020"},
    )
    assert resposta.status_code == 400