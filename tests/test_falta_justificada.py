"""Falta justificada.

Registra o motivo da ausência, conta como falta nos números e aparece
separada no relatório.
"""

from datetime import date, time

import app as modulo_app
from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from models import Appointment, Patient, TreatmentCycle, User, db

HOJE = date(2026, 9, 14)
FUTURO = date(2030, 1, 15)
MOTIVO = "Consulta médica no mesmo horário."


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def fixar_hoje(monkeypatch, dia=HOJE):
    monkeypatch.setattr(modulo_app, "hoje", lambda: dia)


def montar(app, fisioterapeuta_id, data=HOJE, status="AGENDADO", hora=time(9, 0)):
    with app.app_context():
        paciente = db.session.scalar(db.select(Patient))
        if paciente is None:
            paciente = Patient(
                nome="Ivani Souza", fisioterapeuta_id=fisioterapeuta_id, ativo=True
            )
            db.session.add(paciente)
            db.session.flush()

        ciclo = db.session.scalar(db.select(TreatmentCycle))
        if ciclo is None:
            ciclo = TreatmentCycle(
                paciente_id=paciente.id,
                fisioterapeuta_id=fisioterapeuta_id,
                regiao="OMBRO",
                modalidade="INDIVIDUAL",
                data_avaliacao=date(2026, 9, 1),
                total_sessoes=10,
                status="ATIVO",
            )
            db.session.add(ciclo)
            db.session.flush()

        agendamento = Appointment(
            tipo="SESSAO",
            paciente_id=paciente.id,
            ciclo_id=ciclo.id,
            fisioterapeuta_id=fisioterapeuta_id,
            data=data,
            hora=hora,
            duracao_min=30,
            status=status,
        )
        db.session.add(agendamento)
        db.session.commit()
        return paciente.id, agendamento.id


def marcar(client, agendamento_id, status, justificativa=None):
    dados = {"status": status}
    if justificativa is not None:
        dados["justificativa"] = justificativa
    return client.post(f"/agendamentos/{agendamento_id}/status", data=dados)


def buscar(app, agendamento_id):
    with app.app_context():
        return db.session.get(Appointment, agendamento_id)


# ----------------------------------------------------------------------
# Registro
# ----------------------------------------------------------------------


def test_registrar_falta_justificada_guarda_o_motivo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = montar(app, id_fisio)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    marcar(client, id_agendamento, "FALTA_JUSTIFICADA", MOTIVO)

    agendamento = buscar(app, id_agendamento)
    assert agendamento.status == "FALTA_JUSTIFICADA"
    assert agendamento.observacoes == MOTIVO


def test_falta_justificada_sem_motivo_e_recusada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = montar(app, id_fisio)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    marcar(client, id_agendamento, "FALTA_JUSTIFICADA", "   ")

    assert buscar(app, id_agendamento).status == "AGENDADO"


def test_falta_justificada_em_data_futura_e_recusada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = montar(app, id_fisio, data=FUTURO)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    marcar(client, id_agendamento, "FALTA_JUSTIFICADA", MOTIVO)

    assert buscar(app, id_agendamento).status == "AGENDADO"


def test_outros_status_nao_mexem_nas_observacoes(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = montar(app, id_fisio)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    marcar(client, id_agendamento, "REALIZADO", "texto que deve ser ignorado")

    agendamento = buscar(app, id_agendamento)
    assert agendamento.status == "REALIZADO"
    assert agendamento.observacoes is None


# ----------------------------------------------------------------------
# Efeito nas telas
# ----------------------------------------------------------------------


def test_agenda_oferece_a_opcao_e_mostra_o_rotulo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = montar(app, id_fisio, status="FALTA_JUSTIFICADA")

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    corpo = client.get(f"/agenda?data={HOJE.isoformat()}").get_data(as_text=True)

    assert 'value="FALTA_JUSTIFICADA"' in corpo
    assert "Falta justificada" in corpo


def test_ficha_mostra_o_rotulo_sem_quebrar(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente, _ = montar(app, id_fisio, status="FALTA_JUSTIFICADA")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.get(f"/pacientes/{id_paciente}")

    assert resposta.status_code == 200
    assert "Falta justificada" in resposta.get_data(as_text=True)


def test_prontuario_mostra_o_rotulo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente, _ = montar(app, id_fisio, status="FALTA_JUSTIFICADA")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get(f"/pacientes/{id_paciente}/prontuario").get_data(as_text=True)

    assert "Falta justificada" in corpo


def test_dashboard_conta_justificada_como_falta(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    montar(app, id_fisio, status="FALTOU")
    montar(app, id_fisio, status="FALTA_JUSTIFICADA", hora=time(10, 0))
    montar(app, id_fisio, status="REALIZADO", hora=time(11, 0))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/dashboard/fisioterapeuta").get_data(as_text=True)

    assert "2 faltas" in corpo


def test_relatorio_separa_falta_de_justificada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    montar(app, id_fisio, status="FALTOU")
    montar(app, id_fisio, status="FALTA_JUSTIFICADA", hora=time(10, 0))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/relatorios?mes=9&ano=2026").get_data(as_text=True)

    assert "Justificadas" in corpo
    assert "1 justificada" in corpo


def test_evolucao_em_falta_justificada_e_recusada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = montar(app, id_fisio, status="FALTA_JUSTIFICADA")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    client.post(
        f"/agendamentos/{id_agendamento}/evolucao", data={"descricao": "tentativa"}
    )

    with app.app_context():
        assert db.session.scalar(db.select(db.func.count())) is not None
        from models import Evolution

        assert db.session.scalar(db.select(db.func.count(Evolution.id))) == 0
