"""Reposição automática de sessões.

Regra da clínica: cancelamento pelo setor e falta justificada não consomem
sessão do ciclo — a sessão é reagendada na sequência, depois da última já
marcada. Falta não avisada não dá direito a reposição, e grupo não repõe.
"""

from datetime import date, time, timedelta

import app as modulo_app
from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from models import Appointment, Holiday, Patient, TreatmentCycle, User, db

# 05/10/2026 é uma segunda-feira.
PRIMEIRA = date(2026, 10, 5)
HOJE = date(2026, 9, 28)


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def fixar_hoje(monkeypatch, dia=HOJE):
    monkeypatch.setattr(modulo_app, "hoje", lambda: dia)


def montar_ciclo(app, fisioterapeuta_id, sessoes=4, modalidade="INDIVIDUAL"):
    """Cria paciente, ciclo e `sessoes` segundas-feiras seguidas às 09:00."""
    with app.app_context():
        paciente = Patient(
            nome="Ivani Barreto", fisioterapeuta_id=fisioterapeuta_id, ativo=True
        )
        db.session.add(paciente)
        db.session.flush()

        ciclo = TreatmentCycle(
            paciente_id=paciente.id,
            fisioterapeuta_id=fisioterapeuta_id,
            regiao="OMBRO",
            modalidade=modalidade,
            data_avaliacao=date(2026, 10, 1),
            total_sessoes=10,
            status="ATIVO",
        )
        db.session.add(ciclo)
        db.session.flush()

        ids = []
        for n in range(sessoes):
            agendamento = Appointment(
                tipo="SESSAO",
                paciente_id=paciente.id,
                ciclo_id=ciclo.id,
                fisioterapeuta_id=fisioterapeuta_id,
                data=PRIMEIRA + timedelta(days=7 * n),
                hora=time(9, 0),
                duracao_min=30,
                status="AGENDADO",
            )
            db.session.add(agendamento)
            db.session.flush()
            ids.append(agendamento.id)

        db.session.commit()
        return ciclo.id, ids


def marcar(client, agendamento_id, status, justificativa=None):
    dados = {"status": status}
    if justificativa is not None:
        dados["justificativa"] = justificativa
    return client.post(f"/agendamentos/{agendamento_id}/status", data=dados)


def sessoes(app, ciclo_id):
    with app.app_context():
        return (
            Appointment.query.filter_by(ciclo_id=ciclo_id)
            .order_by(Appointment.data)
            .all()
        )


def ultima_data(app, ciclo_id):
    return sessoes(app, ciclo_id)[-1].data


# ----------------------------------------------------------------------
# Quando a reposição acontece
# ----------------------------------------------------------------------


def test_falta_justificada_gera_reposicao_no_fim_do_ciclo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo, ids = montar_ciclo(app, id_fisio, sessoes=4)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    marcar(client, ids[0], "FALTA_JUSTIFICADA", "Consulta médica.")

    lista = sessoes(app, id_ciclo)
    assert len(lista) == 5
    # A última sessão era 26/10; a reposição cai na segunda seguinte.
    assert lista[-1].data == PRIMEIRA + timedelta(days=7 * 4)
    assert lista[-1].hora == time(9, 0)
    assert lista[-1].status == "AGENDADO"


def test_cancelamento_pelo_setor_gera_reposicao(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo, ids = montar_ciclo(app, id_fisio, sessoes=3)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    marcar(client, ids[1], "CANCELADO")

    assert len(sessoes(app, id_ciclo)) == 4


def test_falta_nao_avisada_nao_repoe(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo, ids = montar_ciclo(app, id_fisio, sessoes=3)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    marcar(client, ids[0], "FALTOU")

    assert len(sessoes(app, id_ciclo)) == 3


def test_comparecimento_nao_repoe(client, app, monkeypatch):
    fixar_hoje(monkeypatch, PRIMEIRA)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo, ids = montar_ciclo(app, id_fisio, sessoes=3)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    marcar(client, ids[0], "REALIZADO")

    assert len(sessoes(app, id_ciclo)) == 3


def test_grupo_nao_repoe(client, app, monkeypatch):
    """Tratamento em grupo é fechado: a clínica não repõe encontro perdido."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo, ids = montar_ciclo(app, id_fisio, sessoes=3, modalidade="GRUPO")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    marcar(client, ids[0], "FALTA_JUSTIFICADA", "Viagem.")

    assert len(sessoes(app, id_ciclo)) == 3


def test_sessao_sem_ciclo_nao_repoe(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    with app.app_context():
        paciente = Patient(nome="Avulso", fisioterapeuta_id=id_fisio, ativo=True)
        db.session.add(paciente)
        db.session.flush()
        avulso = Appointment(
            tipo="AVALIACAO",
            paciente_id=paciente.id,
            fisioterapeuta_id=id_fisio,
            data=PRIMEIRA,
            hora=time(9, 0),
            duracao_min=30,
            status="AGENDADO",
        )
        db.session.add(avulso)
        db.session.commit()
        id_avulso = avulso.id

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    marcar(client, id_avulso, "CANCELADO")

    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Appointment.id))) == 1


# ----------------------------------------------------------------------
# Como a data é escolhida
# ----------------------------------------------------------------------


def test_reposicao_mantem_dia_da_semana_e_horario(client, app, monkeypatch):
    """O ciclo pode ter dias variados; a reposição segue a sessão perdida."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo, ids = montar_ciclo(app, id_fisio, sessoes=2)

    with app.app_context():
        sexta = db.session.get(Appointment, ids[1])
        sexta.data = PRIMEIRA + timedelta(days=4)  # sexta-feira
        sexta.hora = time(14, 30)
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    marcar(client, ids[1], "FALTA_JUSTIFICADA", "Exame.")

    nova = sessoes(app, id_ciclo)[-1]
    assert nova.data.weekday() == 4
    assert nova.hora == time(14, 30)


def test_reposicao_pula_feriado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo, ids = montar_ciclo(app, id_fisio, sessoes=2)

    esperada = PRIMEIRA + timedelta(days=14)
    with app.app_context():
        db.session.add(
            Holiday(data=esperada, nome="Feriado municipal", tipo="MUNICIPAL")
        )
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    marcar(client, ids[0], "FALTA_JUSTIFICADA", "Consulta.")

    assert ultima_data(app, id_ciclo) == esperada + timedelta(days=7)


def test_reposicao_pula_horario_cheio(client, app, monkeypatch):
    """O limite de 2 por horário vale também para a reposição."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo, ids = montar_ciclo(app, id_fisio, sessoes=2)

    cheia = PRIMEIRA + timedelta(days=14)
    with app.app_context():
        outro = Patient(nome="Outro", fisioterapeuta_id=id_fisio, ativo=True)
        db.session.add(outro)
        db.session.flush()
        for _ in range(2):
            db.session.add(
                Appointment(
                    tipo="SESSAO",
                    paciente_id=outro.id,
                    fisioterapeuta_id=id_fisio,
                    data=cheia,
                    hora=time(9, 0),
                    duracao_min=30,
                    status="AGENDADO",
                )
            )
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    marcar(client, ids[0], "FALTA_JUSTIFICADA", "Consulta.")

    assert ultima_data(app, id_ciclo) == cheia + timedelta(days=7)


def test_reposicao_nao_duplica_ao_salvar_de_novo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo, ids = montar_ciclo(app, id_fisio, sessoes=2)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    marcar(client, ids[0], "FALTA_JUSTIFICADA", "Consulta.")
    marcar(client, ids[0], "AGENDADO")
    marcar(client, ids[0], "FALTA_JUSTIFICADA", "Consulta.")

    assert len(sessoes(app, id_ciclo)) == 3


def test_reposicao_fica_identificada_na_observacao(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo, ids = montar_ciclo(app, id_fisio, sessoes=2)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    marcar(client, ids[0], "CANCELADO")

    nova = sessoes(app, id_ciclo)[-1]
    assert "Reposição da sessão de 05/10/2026" in nova.observacoes


def test_ciclo_encerrado_nao_repoe(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo, ids = montar_ciclo(app, id_fisio, sessoes=2)

    with app.app_context():
        db.session.get(TreatmentCycle, id_ciclo).status = "ALTA"
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    marcar(client, ids[0], "CANCELADO")

    assert len(sessoes(app, id_ciclo)) == 2


def test_admin_tambem_dispara_a_reposicao(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo, ids = montar_ciclo(app, id_fisio, sessoes=2)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    marcar(client, ids[0], "FALTA_JUSTIFICADA", "Avisou na recepção.")

    assert len(sessoes(app, id_ciclo)) == 3
