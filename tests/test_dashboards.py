"""Dashboards de admin e fisioterapeuta.

Os painéis mostram números reais da operação, com o escopo de cada perfil.
"""

from datetime import date, time, timedelta

import app as modulo_app
from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from models import Appointment, Group, Patient, TreatmentCycle, User, db

HOJE = date(2026, 9, 14)


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def fixar_hoje(monkeypatch):
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)


def criar_paciente(app, fisioterapeuta_id, nome="Ana Prado"):
    with app.app_context():
        paciente = Patient(nome=nome, fisioterapeuta_id=fisioterapeuta_id, ativo=True)
        db.session.add(paciente)
        db.session.commit()
        return paciente.id


def criar_agendamento(app, fisioterapeuta_id, paciente_id, data=HOJE, **campos):
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
# Dashboard do fisioterapeuta
# ----------------------------------------------------------------------


def test_dashboard_do_fisioterapeuta_conta_atendimentos_de_hoje(
    client, app, monkeypatch
):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)
    criar_agendamento(app, id_fisio, id_paciente)
    criar_agendamento(app, id_fisio, id_paciente, hora=time(10, 0))
    criar_agendamento(app, id_fisio, id_paciente, data=HOJE + timedelta(days=1))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/dashboard/fisioterapeuta").get_data(as_text=True)

    assert "Ana Prado" in corpo
    assert "agenda em preparação" not in corpo
    assert "próxima etapa" not in corpo


def test_dashboard_do_fisioterapeuta_mostra_presencas_do_mes(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)
    criar_agendamento(app, id_fisio, id_paciente, status="REALIZADO")
    criar_agendamento(app, id_fisio, id_paciente, hora=time(10, 0), status="REALIZADO")
    criar_agendamento(app, id_fisio, id_paciente, hora=time(11, 0), status="FALTOU")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/dashboard/fisioterapeuta").get_data(as_text=True)

    assert "1 falta(s)" in corpo
    assert "67% de presença" in corpo


def test_dashboard_do_fisioterapeuta_nao_mostra_agenda_de_outro(
    client, app, monkeypatch
):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_admin = id_do_usuario(app, "admin@teste.com")
    criar_agendamento(
        app, id_admin, criar_paciente(app, id_admin, nome="Paciente do admin")
    )
    criar_agendamento(
        app, id_fisio, criar_paciente(app, id_fisio, nome="Paciente do fisio")
    )

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/dashboard/fisioterapeuta").get_data(as_text=True)

    assert "Paciente do fisio" in corpo
    assert "Paciente do admin" not in corpo


def test_dashboard_do_fisioterapeuta_lista_seus_grupos(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_admin = id_do_usuario(app, "admin@teste.com")
    with app.app_context():
        db.session.add_all(
            [
                Group(
                    nome="Grupo do fisio",
                    regiao="OMBRO",
                    fisioterapeuta_id=id_fisio,
                    dia_semana=1,
                    hora=time(8, 0),
                    capacidade_max=14,
                    ativo=True,
                ),
                Group(
                    nome="Grupo do admin",
                    regiao="JOELHO",
                    fisioterapeuta_id=id_admin,
                    dia_semana=2,
                    hora=time(9, 0),
                    capacidade_max=14,
                    ativo=True,
                ),
            ]
        )
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/dashboard/fisioterapeuta").get_data(as_text=True)

    assert "Grupo do fisio" in corpo
    assert "Grupo do admin" not in corpo


def test_dashboard_do_fisioterapeuta_sem_dados_nao_quebra(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    resposta = client.get("/dashboard/fisioterapeuta")

    assert resposta.status_code == 200
    assert "Nenhum atendimento hoje" in resposta.get_data(as_text=True)


# ----------------------------------------------------------------------
# Dashboard do admin
# ----------------------------------------------------------------------


def test_dashboard_do_admin_mostra_a_clinica_inteira(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_admin = id_do_usuario(app, "admin@teste.com")
    criar_agendamento(
        app, id_fisio, criar_paciente(app, id_fisio, nome="Paciente do fisio")
    )
    criar_agendamento(
        app,
        id_admin,
        criar_paciente(app, id_admin, nome="Paciente do admin"),
        hora=time(10, 0),
    )

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    corpo = client.get("/dashboard/admin").get_data(as_text=True)

    assert "Paciente do fisio" in corpo
    assert "Paciente do admin" in corpo


def test_dashboard_do_admin_conta_pacientes_e_ciclos(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)
    with app.app_context():
        db.session.add(
            TreatmentCycle(
                paciente_id=id_paciente,
                fisioterapeuta_id=id_fisio,
                regiao="OMBRO",
                modalidade="INDIVIDUAL",
                data_avaliacao=date(2026, 9, 1),
                total_sessoes=10,
                status="ATIVO",
            )
        )
        db.session.commit()

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    corpo = client.get("/dashboard/admin").get_data(as_text=True)

    assert "1 ciclo(s) em tratamento" in corpo


def test_dashboard_do_admin_nao_tem_mais_o_roadmap_antigo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    corpo = client.get("/dashboard/admin").get_data(as_text=True)

    assert "Próxima etapa" not in corpo
    assert "Planejado" not in corpo


def test_fisioterapeuta_nao_abre_o_dashboard_do_admin(client):
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert client.get("/dashboard/admin").status_code == 403
