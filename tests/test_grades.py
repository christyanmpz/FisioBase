"""Grades de impressão: semanal por profissional e diária do setor.

Reproduzem as planilhas que a clínica usa hoje.
"""

from datetime import date, time, timedelta

import app as modulo_app
from conftest import SENHA_ADMIN, SENHA_FISIO, criar_usuario, fazer_login
from models import PHYSIOTHERAPIST_PROFILE, Appointment, Patient, User, db

SENHA_NOVA = "Nova@1234"
SEGUNDA = date(2026, 9, 14)
SEXTA = SEGUNDA + timedelta(days=4)
SABADO = SEGUNDA + timedelta(days=5)


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def fixar_hoje(monkeypatch, dia=SEGUNDA):
    monkeypatch.setattr(modulo_app, "hoje", lambda: dia)


def criar_paciente(app, fisioterapeuta_id, nome="Ana Prado"):
    with app.app_context():
        paciente = Patient(nome=nome, fisioterapeuta_id=fisioterapeuta_id, ativo=True)
        db.session.add(paciente)
        db.session.commit()
        return paciente.id


def agendar(app, fisioterapeuta_id, paciente_id, data=SEGUNDA, **campos):
    dados = {
        "tipo": "SESSAO",
        "paciente_id": paciente_id,
        "fisioterapeuta_id": fisioterapeuta_id,
        "data": data,
        "hora": time(9, 0),
        "duracao_min": 30,
        "status": "AGENDADO",
    }
    dados.update(campos)
    with app.app_context():
        agendamento = Appointment(**dados)
        db.session.add(agendamento)
        db.session.commit()
        return agendamento.id


# ----------------------------------------------------------------------
# Grade semanal
# ----------------------------------------------------------------------


def test_grade_semanal_mostra_a_semana_do_profissional(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio, nome="Dirceu Almeida")
    agendar(app, id_fisio, id_paciente, data=SEGUNDA)
    agendar(app, id_fisio, id_paciente, data=SEXTA, hora=time(14, 0))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/agenda/semana").get_data(as_text=True)

    assert corpo.count("Dirceu Almeida") == 2
    assert "07:30" in corpo
    assert "15:30" in corpo


def test_grade_semanal_abre_na_segunda_da_semana(client, app, monkeypatch):
    fixar_hoje(monkeypatch, SEGUNDA + timedelta(days=3))
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)
    agendar(app, id_fisio, id_paciente, data=SEGUNDA)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/agenda/semana").get_data(as_text=True)

    assert SEGUNDA.strftime("%d/%m") in corpo
    assert SEXTA.strftime("%d/%m") in corpo


def test_grade_semanal_nao_mostra_fim_de_semana(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    corpo = client.get("/agenda/semana").get_data(as_text=True)

    assert SABADO.strftime("%d/%m") not in corpo


def test_grade_semanal_ignora_cancelados(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio, nome="Paciente Cancelado")
    agendar(app, id_fisio, id_paciente, status="CANCELADO")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/agenda/semana").get_data(as_text=True)

    assert "Paciente Cancelado" not in corpo


def test_fisioterapeuta_ve_so_a_propria_grade(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_admin = id_do_usuario(app, "admin@teste.com")
    agendar(app, id_fisio, criar_paciente(app, id_fisio, nome="Paciente do fisio"))
    agendar(
        app,
        id_admin,
        criar_paciente(app, id_admin, nome="Paciente do admin"),
        hora=time(10, 0),
    )

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/agenda/semana").get_data(as_text=True)

    assert "Paciente do fisio" in corpo
    assert "Paciente do admin" not in corpo


def test_admin_escolhe_a_grade_de_outro_profissional(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    agendar(app, id_fisio, criar_paciente(app, id_fisio, nome="Paciente do fisio"))

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    corpo = client.get(f"/agenda/semana?fisioterapeuta_id={id_fisio}").get_data(
        as_text=True
    )

    assert "Paciente do fisio" in corpo


def test_grade_semanal_marca_a_triagem(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)
    agendar(app, id_fisio, id_paciente, tipo="AVALIACAO")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/agenda/semana").get_data(as_text=True)

    assert "triagem" in corpo


def test_grade_semanal_exige_login(client):
    resposta = client.get("/agenda/semana")

    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


# ----------------------------------------------------------------------
# Grade diária
# ----------------------------------------------------------------------


def test_grade_diaria_mostra_profissionais_lado_a_lado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    with app.app_context():
        db.session.add(
            criar_usuario(
                "Outra Fisio", "outra@teste.com", SENHA_NOVA, PHYSIOTHERAPIST_PROFILE
            )
        )
        db.session.commit()
    id_outra = id_do_usuario(app, "outra@teste.com")

    agendar(app, id_fisio, criar_paciente(app, id_fisio, nome="Paciente um"))
    agendar(
        app,
        id_outra,
        criar_paciente(app, id_outra, nome="Paciente dois"),
        hora=time(10, 0),
    )

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    corpo = client.get("/agenda/dia").get_data(as_text=True)

    assert "Paciente um" in corpo
    assert "Paciente dois" in corpo


def test_grade_diaria_usa_a_data_pedida(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio, nome="Paciente de sexta")
    agendar(app, id_fisio, id_paciente, data=SEXTA)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    assert "Paciente de sexta" not in client.get("/agenda/dia").get_data(as_text=True)
    corpo = client.get(f"/agenda/dia?data={SEXTA.isoformat()}").get_data(as_text=True)
    assert "Paciente de sexta" in corpo


def test_grade_diaria_do_fisioterapeuta_mostra_so_a_dele(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_admin = id_do_usuario(app, "admin@teste.com")
    agendar(app, id_fisio, criar_paciente(app, id_fisio, nome="Paciente do fisio"))
    agendar(
        app,
        id_admin,
        criar_paciente(app, id_admin, nome="Paciente do admin"),
        hora=time(10, 0),
    )

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/agenda/dia").get_data(as_text=True)

    assert "Paciente do fisio" in corpo
    assert "Paciente do admin" not in corpo


def test_grade_diaria_com_data_invalida_abre_hoje(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    corpo = client.get("/agenda/dia?data=nao-e-data").get_data(as_text=True)

    assert SEGUNDA.strftime("%d/%m/%Y") in corpo
