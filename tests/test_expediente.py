"""Expediente da clínica na agenda.

Grade de 07:30 às 15:30, de 30 em 30 minutos, sem o horário de almoço.
Atendimento de segunda a sexta, nunca em data que já passou.
"""

from datetime import date, timedelta

import app as modulo_app
from conftest import SENHA_FISIO, fazer_login
from models import Appointment, Patient, User, db

GRADE_ESPERADA = [
    "07:30",
    "08:00",
    "08:30",
    "09:00",
    "09:30",
    "10:00",
    "10:30",
    "11:00",
    "11:30",
    "12:30",
    "13:00",
    "13:30",
    "14:00",
    "14:30",
    "15:00",
    "15:30",
]


def proxima_segunda():
    hoje = date.today()
    return hoje + timedelta(days=(7 - hoje.weekday()) or 7)


DIA_UTIL = proxima_segunda()
SABADO = DIA_UTIL + timedelta(days=5)
DOMINGO = DIA_UTIL + timedelta(days=6)


def criar_paciente(app, nome="Bruno Dias"):
    with app.app_context():
        id_fisio = db.session.scalar(
            db.select(User).where(User.email == "fisio@teste.com")
        ).id
        paciente = Patient(nome=nome, fisioterapeuta_id=id_fisio, ativo=True)
        db.session.add(paciente)
        db.session.commit()
        return paciente.id


def agendar(client, paciente_id, data, hora):
    return client.post(
        "/agenda/novo",
        data={
            "paciente_id": str(paciente_id),
            "tipo": "AVALIACAO",
            "data": data.isoformat(),
            "hora": hora,
        },
    )


def contar(app):
    with app.app_context():
        return db.session.scalar(db.select(db.func.count(Appointment.id)))


# ----------------------------------------------------------------------
# A grade de horários
# ----------------------------------------------------------------------


def test_grade_vai_de_0730_a_1530_sem_almoco():
    assert modulo_app.HORARIOS == GRADE_ESPERADA


def test_formulario_oferece_a_grade_nova(client, app):
    criar_paciente(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    corpo = client.get("/agenda/novo").get_data(as_text=True)

    assert '<option value="07:30">' in corpo
    assert '<option value="15:30">' in corpo
    assert '<option value="12:00">' not in corpo
    assert '<option value="16:00">' not in corpo
    assert '<option value="16:30">' not in corpo


def test_agendar_no_primeiro_horario_do_dia(client, app):
    id_paciente = criar_paciente(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert agendar(client, id_paciente, DIA_UTIL, "07:30").status_code == 302
    assert contar(app) == 1


def test_agendar_no_ultimo_horario_do_dia(client, app):
    id_paciente = criar_paciente(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert agendar(client, id_paciente, DIA_UTIL, "15:30").status_code == 302
    assert contar(app) == 1


def test_horario_de_almoco_e_recusado(client, app):
    id_paciente = criar_paciente(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert agendar(client, id_paciente, DIA_UTIL, "12:00").status_code == 400
    assert contar(app) == 0


def test_horario_apos_o_expediente_e_recusado(client, app):
    id_paciente = criar_paciente(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert agendar(client, id_paciente, DIA_UTIL, "16:30").status_code == 400
    assert contar(app) == 0


def test_horario_antes_do_expediente_e_recusado(client, app):
    id_paciente = criar_paciente(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert agendar(client, id_paciente, DIA_UTIL, "07:00").status_code == 400
    assert contar(app) == 0


def test_horario_fora_da_meia_hora_e_recusado(client, app):
    id_paciente = criar_paciente(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert agendar(client, id_paciente, DIA_UTIL, "09:15").status_code == 400
    assert contar(app) == 0


# ----------------------------------------------------------------------
# Dias de atendimento
# ----------------------------------------------------------------------


def test_sabado_e_recusado(client, app):
    id_paciente = criar_paciente(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert agendar(client, id_paciente, SABADO, "09:00").status_code == 400
    assert contar(app) == 0


def test_domingo_e_recusado(client, app):
    id_paciente = criar_paciente(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert agendar(client, id_paciente, DOMINGO, "09:00").status_code == 400
    assert contar(app) == 0


def test_sexta_feira_e_aceita(client, app):
    id_paciente = criar_paciente(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    sexta = DIA_UTIL + timedelta(days=4)
    assert agendar(client, id_paciente, sexta, "09:00").status_code == 302
    assert contar(app) == 1


# ----------------------------------------------------------------------
# Data que já passou
# ----------------------------------------------------------------------


def test_data_passada_e_recusada(client, app):
    id_paciente = criar_paciente(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    ontem = date.today() - timedelta(days=1)
    assert agendar(client, id_paciente, ontem, "09:00").status_code == 400
    assert contar(app) == 0


def test_agendar_para_hoje_continua_permitido(client, app, monkeypatch):
    """Encaixe no mesmo dia: a recusa é só para data anterior a hoje."""
    monkeypatch.setattr(modulo_app, "hoje", lambda: DIA_UTIL)
    id_paciente = criar_paciente(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert agendar(client, id_paciente, DIA_UTIL, "09:00").status_code == 302
    assert contar(app) == 1


def test_formulario_tem_campo_de_busca_de_paciente(client, app):
    criar_paciente(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    corpo = client.get("/agenda/novo").get_data(as_text=True)

    assert 'data-busca-de="paciente_id"' in corpo
