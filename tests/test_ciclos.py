"""Testes dos ciclos de tratamento."""

from datetime import date

from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from models import Patient, TreatmentCycle, User, db


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def criar_paciente(app, nome, fisioterapeuta_id):
    with app.app_context():
        paciente = Patient(nome=nome, fisioterapeuta_id=fisioterapeuta_id, ativo=True)
        db.session.add(paciente)
        db.session.commit()
        return paciente.id


def abrir_ciclo(client, paciente_id, **campos):
    dados = {
        "data_avaliacao": "2026-09-01",
        "regiao": "JOELHO",
        "modalidade": "INDIVIDUAL",
        "total_sessoes": "10",
    }
    dados.update(campos)
    return client.post(
        f"/pacientes/{paciente_id}/ciclos/novo", data=dados, follow_redirects=True
    )


def test_abrir_ciclo_grava_no_banco(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    abrir_ciclo(client, id_paciente)

    with app.app_context():
        ciclo = db.session.scalar(
            db.select(TreatmentCycle).where(TreatmentCycle.paciente_id == id_paciente)
        )
        assert ciclo is not None
        assert ciclo.regiao == "JOELHO"
        assert ciclo.status == "ATIVO"
        assert ciclo.total_sessoes == 10
        assert ciclo.data_avaliacao == date(2026, 9, 1)


def test_paciente_pode_ter_dois_ciclos_ativos(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    abrir_ciclo(client, id_paciente, regiao="JOELHO")
    abrir_ciclo(client, id_paciente, regiao="COLUNA")

    with app.app_context():
        ciclos = db.session.scalars(
            db.select(TreatmentCycle).where(TreatmentCycle.paciente_id == id_paciente)
        ).all()
        assert len(ciclos) == 2
        assert all(ciclo.status == "ATIVO" for ciclo in ciclos)


def test_regiao_invalida_e_recusada(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(
        f"/pacientes/{id_paciente}/ciclos/novo",
        data={"data_avaliacao": "2026-09-01", "regiao": "COTOVELO"},
    )
    assert resposta.status_code == 400


def test_data_invalida_nao_derruba_a_pagina(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(
        f"/pacientes/{id_paciente}/ciclos/novo",
        data={"data_avaliacao": "31/02/2026", "regiao": "JOELHO"},
    )
    assert resposta.status_code == 400


def test_numero_de_sessoes_fora_do_limite_e_recusado(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(
        f"/pacientes/{id_paciente}/ciclos/novo",
        data={
            "data_avaliacao": "2026-09-01",
            "regiao": "JOELHO",
            "total_sessoes": "999",
        },
    )
    assert resposta.status_code == 400


def test_fisioterapeuta_nao_ve_ciclos_de_paciente_alheio(client, app):
    id_admin = id_do_usuario(app, "admin@teste.com")
    id_alheio = criar_paciente(app, "Paciente Do Admin", id_admin)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    assert client.get(f"/pacientes/{id_alheio}/ciclos").status_code == 403
    assert client.get(f"/pacientes/{id_alheio}/ciclos/novo").status_code == 403


def test_encerrar_ciclo_registra_status_e_data(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    abrir_ciclo(client, id_paciente)

    with app.app_context():
        ciclo_id = db.session.scalar(
            db.select(TreatmentCycle).where(TreatmentCycle.paciente_id == id_paciente)
        ).id

    client.post(
        f"/ciclos/{ciclo_id}/encerrar", data={"status": "ALTA"}, follow_redirects=True
    )

    with app.app_context():
        ciclo = db.session.get(TreatmentCycle, ciclo_id)
        assert ciclo.status == "ALTA"
        assert ciclo.data_alta == date.today()


def test_status_de_encerramento_invalido_nao_altera_o_ciclo(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    abrir_ciclo(client, id_paciente)

    with app.app_context():
        ciclo_id = db.session.scalar(
            db.select(TreatmentCycle).where(TreatmentCycle.paciente_id == id_paciente)
        ).id

    client.post(
        f"/ciclos/{ciclo_id}/encerrar",
        data={"status": "QUALQUER"},
        follow_redirects=True,
    )

    with app.app_context():
        assert db.session.get(TreatmentCycle, ciclo_id).status == "ATIVO"
