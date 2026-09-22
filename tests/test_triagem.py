"""Agenda de triagem: horários fixos, avaliação normal e urgência.

A triagem é o primeiro contato com o paciente e acontece antes de existir
ciclo de tratamento. Cada profissional reserva alguns horários da semana
para isso; fratura, AVC e pré/pós-operatório entram como urgência, fora
da grade.
"""

from datetime import date, time, timedelta

import app as modulo_app
from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from models import Appointment, Patient, ScreeningSlot, User, db

# 05/10/2026 é uma segunda-feira.
SEGUNDA = date(2026, 10, 5)
QUARTA = SEGUNDA + timedelta(days=2)
HOJE = date(2026, 9, 28)


def fixar_hoje(monkeypatch, dia=HOJE):
    monkeypatch.setattr(modulo_app, "hoje", lambda: dia)


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def criar_paciente(app, id_fisio, nome="Ana Prado"):
    with app.app_context():
        paciente = Patient(nome=nome, fisioterapeuta_id=id_fisio, ativo=True)
        db.session.add(paciente)
        db.session.commit()
        return paciente.id


def reservar(app, id_fisio, dia_semana=0, hora=time(13, 30)):
    with app.app_context():
        slot = ScreeningSlot(
            fisioterapeuta_id=id_fisio, dia_semana=dia_semana, hora=hora, ativo=True
        )
        db.session.add(slot)
        db.session.commit()
        return slot.id


def agendar(client, id_paciente, data, hora, **extra):
    dados = {
        "paciente_id": str(id_paciente),
        "data": data.isoformat(),
        "hora": hora,
    }
    dados.update(extra)
    return client.post("/triagem/agendar", data=dados, follow_redirects=True)


def avaliacoes(app):
    with app.app_context():
        return Appointment.query.filter_by(tipo="AVALIACAO").all()


# ----------------------------------------------------------------------
# Horários fixos
# ----------------------------------------------------------------------


def test_reserva_um_horario_de_triagem(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    client.post(
        "/triagem/horarios",
        data={"dia_semana": "0", "hora": "13:30"},
        follow_redirects=True,
    )

    with app.app_context():
        slot = db.session.scalar(db.select(ScreeningSlot))
        assert slot is not None
        assert slot.dia_semana == 0
        assert slot.hora == time(13, 30)
        assert slot.ativo is True


def test_horario_repetido_e_recusado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    reservar(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(
        "/triagem/horarios",
        data={"dia_semana": "0", "hora": "13:30"},
        follow_redirects=True,
    )

    assert "já existe" in resposta.get_data(as_text=True)
    with app.app_context():
        assert ScreeningSlot.query.count() == 1


def test_fim_de_semana_e_recusado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    resposta = client.post(
        "/triagem/horarios",
        data={"dia_semana": "5", "hora": "13:30"},
        follow_redirects=True,
    )

    assert "segunda a sexta" in resposta.get_data(as_text=True)
    with app.app_context():
        assert ScreeningSlot.query.count() == 0


def test_remover_desativa_em_vez_de_apagar(client, app, monkeypatch):
    """A linha fica: o histórico de quem passou por ali depende dela."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_slot = reservar(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    client.post(f"/triagem/horarios/{id_slot}/remover", follow_redirects=True)

    with app.app_context():
        slot = db.session.get(ScreeningSlot, id_slot)
        assert slot is not None
        assert slot.ativo is False


def test_fisioterapeuta_nao_remove_horario_de_outro(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_admin = id_do_usuario(app, "admin@teste.com")
    id_slot = reservar(app, id_admin)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(f"/triagem/horarios/{id_slot}/remover")

    assert resposta.status_code == 403


# ----------------------------------------------------------------------
# Agendar a avaliação
# ----------------------------------------------------------------------


def test_agenda_avaliacao_em_horario_de_triagem(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    reservar(app, id_fisio, dia_semana=0, hora=time(13, 30))
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    agendar(client, id_paciente, SEGUNDA, "13:30")

    lista = avaliacoes(app)
    assert len(lista) == 1
    assert lista[0].data == SEGUNDA
    assert lista[0].hora == time(13, 30)
    assert lista[0].status == "AGENDADO"


def test_fora_do_horario_de_triagem_e_recusado(client, app, monkeypatch):
    """Sem urgência, a avaliação só entra nos horários reservados."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    reservar(app, id_fisio, dia_semana=0, hora=time(13, 30))
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = agendar(client, id_paciente, SEGUNDA, "09:00")

    assert "não tem triagem neste dia e horário" in resposta.get_data(as_text=True)
    assert avaliacoes(app) == []


def test_dia_errado_e_recusado(client, app, monkeypatch):
    """O horário existe, mas na segunda; marcaram para quarta."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    reservar(app, id_fisio, dia_semana=0, hora=time(13, 30))
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = agendar(client, id_paciente, QUARTA, "13:30")

    assert "não tem triagem neste dia e horário" in resposta.get_data(as_text=True)
    assert avaliacoes(app) == []


def test_urgencia_entra_fora_da_grade(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    agendar(
        client,
        id_paciente,
        QUARTA,
        "09:00",
        urgencia="1",
        motivo="Pós-operatório de LCA",
    )

    lista = avaliacoes(app)
    assert len(lista) == 1
    assert lista[0].data == QUARTA
    assert "Pós-operatório de LCA" in lista[0].observacoes


def test_urgencia_sem_motivo_e_recusada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = agendar(client, id_paciente, QUARTA, "09:00", urgencia="1")

    assert "Descreva a urgência" in resposta.get_data(as_text=True)
    assert avaliacoes(app) == []


def test_data_no_passado_e_recusada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    reservar(app, id_fisio, dia_semana=0, hora=time(13, 30))
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = agendar(client, id_paciente, date(2026, 9, 21), "13:30")

    assert "já passou" in resposta.get_data(as_text=True)
    assert avaliacoes(app) == []


def test_horario_cheio_e_recusado(client, app, monkeypatch):
    """O limite de 2 pacientes por horário vale também para a triagem."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    reservar(app, id_fisio, dia_semana=0, hora=time(13, 30))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    for numero in range(3):
        agendar(
            client,
            criar_paciente(app, id_fisio, f"Paciente {numero}"),
            SEGUNDA,
            "13:30",
        )

    assert len(avaliacoes(app)) == 2


# ----------------------------------------------------------------------
# A tela
# ----------------------------------------------------------------------


def test_agenda_mostra_os_horarios_da_semana(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    reservar(app, id_fisio, dia_semana=0, hora=time(13, 30))
    reservar(app, id_fisio, dia_semana=2, hora=time(9, 30))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/triagem?data={SEGUNDA.isoformat()}").get_data(as_text=True)

    assert "13:30" in pagina
    assert "09:30" in pagina
    assert "Livre" in pagina


def test_agenda_mostra_quem_esta_marcado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    reservar(app, id_fisio, dia_semana=0, hora=time(13, 30))
    id_paciente = criar_paciente(app, id_fisio, "Jussara Neves")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    agendar(client, id_paciente, SEGUNDA, "13:30")
    pagina = client.get(f"/triagem?data={SEGUNDA.isoformat()}").get_data(as_text=True)

    assert "Jussara Neves" in pagina


def test_urgencia_aparece_em_bloco_separado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    reservar(app, id_fisio, dia_semana=0, hora=time(13, 30))
    id_paciente = criar_paciente(app, id_fisio, "Marcos Vinicius")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    agendar(
        client,
        id_paciente,
        QUARTA,
        "09:00",
        urgencia="1",
        motivo="Fratura de tornozelo",
    )
    pagina = client.get(f"/triagem?data={SEGUNDA.isoformat()}").get_data(as_text=True)

    assert "Urgências da semana" in pagina
    assert "Fratura de tornozelo" in pagina


def test_sem_horarios_a_tela_explica(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    pagina = client.get("/triagem").get_data(as_text=True)

    assert "Nenhum horário de triagem definido" in pagina


def test_grade_semanal_destaca_o_horario_de_triagem(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    reservar(app, id_fisio, dia_semana=0, hora=time(13, 30))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/agenda/semana?data={SEGUNDA.isoformat()}").get_data(
        as_text=True
    )

    assert "grade-celula--triagem" in pagina
    assert "Horário reservado para triagem" in pagina


def test_fisioterapeuta_ve_so_a_propria_triagem(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_admin = id_do_usuario(app, "admin@teste.com")
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    reservar(app, id_admin, dia_semana=0, hora=time(8, 0))
    reservar(app, id_fisio, dia_semana=0, hora=time(13, 30))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/triagem?data={SEGUNDA.isoformat()}").get_data(as_text=True)

    assert "13:30" in pagina
    assert "08:00" not in pagina


def test_admin_ve_a_triagem_de_todos(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    reservar(app, id_fisio, dia_semana=0, hora=time(13, 30))

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    pagina = client.get(f"/triagem?data={SEGUNDA.isoformat()}").get_data(as_text=True)

    assert "13:30" in pagina
    assert "Rafael Santos" in pagina
