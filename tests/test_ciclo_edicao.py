"""Edição do ciclo e remarcação das próximas sessões.

O paciente arruma outro compromisso e não pode mais na terça. Em vez de
mexer sessão por sessão, o setor remarca o que ainda não aconteceu —
sem tocar no que já passou.
"""

from datetime import date, time, timedelta

import app as modulo_app
from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from models import Appointment, Holiday, Patient, TreatmentCycle, User, db

# 05/10/2026 é uma segunda-feira.
SEGUNDA = date(2026, 10, 5)
HOJE = date(2026, 9, 28)


def fixar_hoje(monkeypatch, dia=HOJE):
    monkeypatch.setattr(modulo_app, "hoje", lambda: dia)


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def montar_ciclo(app, id_fisio, sessoes=4, primeira=SEGUNDA, hora=time(9, 0)):
    """Paciente com ciclo ativo e `sessoes` segundas-feiras seguidas."""
    with app.app_context():
        paciente = Patient(nome="Ivani Barreto", fisioterapeuta_id=id_fisio, ativo=True)
        db.session.add(paciente)
        db.session.flush()

        ciclo = TreatmentCycle(
            paciente_id=paciente.id,
            fisioterapeuta_id=id_fisio,
            regiao="OMBRO",
            modalidade="INDIVIDUAL",
            data_avaliacao=date(2026, 9, 20),
            total_sessoes=10,
            status="ATIVO",
        )
        db.session.add(ciclo)
        db.session.flush()

        for n in range(sessoes):
            db.session.add(
                Appointment(
                    tipo="SESSAO",
                    paciente_id=paciente.id,
                    ciclo_id=ciclo.id,
                    fisioterapeuta_id=id_fisio,
                    data=primeira + timedelta(days=7 * n),
                    hora=hora,
                    duracao_min=30,
                    status="AGENDADO",
                    numero_sessao=n + 1,
                )
            )

        db.session.commit()
        return ciclo.id


def sessoes_do_ciclo(app, id_ciclo):
    with app.app_context():
        return (
            Appointment.query.filter_by(ciclo_id=id_ciclo)
            .order_by(Appointment.data)
            .all()
        )


def remarcar(client, id_ciclo, inicio, hora, dias):
    return client.post(
        f"/ciclos/{id_ciclo}/remarcar",
        data={"inicio": inicio.isoformat(), "hora": hora, "dias": dias},
        follow_redirects=True,
    )


# ----------------------------------------------------------------------
# Editar os dados do ciclo
# ----------------------------------------------------------------------


def test_edita_cid_e_diagnostico_do_ciclo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo = montar_ciclo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    client.post(
        f"/ciclos/{id_ciclo}/editar",
        data={
            "regiao": "COLUNA",
            "cid": "m54.5",
            "diagnostico": "Dor lombar baixa",
            "modalidade": "INDIVIDUAL",
            "data_avaliacao": "2026-09-20",
            "total_sessoes": "10",
        },
        follow_redirects=True,
    )

    with app.app_context():
        ciclo = db.session.get(TreatmentCycle, id_ciclo)
        assert ciclo.regiao == "COLUNA"
        assert ciclo.cid == "M54.5"
        assert ciclo.diagnostico == "Dor lombar baixa"


def test_nao_deixa_reduzir_o_total_abaixo_do_que_ja_esta_agendado(
    client, app, monkeypatch
):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo = montar_ciclo(app, id_fisio, sessoes=4)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(
        f"/ciclos/{id_ciclo}/editar",
        data={
            "regiao": "OMBRO",
            "modalidade": "INDIVIDUAL",
            "data_avaliacao": "2026-09-20",
            "total_sessoes": "2",
        },
    )

    assert "já tem 4 sessões agendadas" in resposta.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(TreatmentCycle, id_ciclo).total_sessoes == 10


def test_outro_fisioterapeuta_nao_edita_o_ciclo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_admin = id_do_usuario(app, "admin@teste.com")
    id_ciclo = montar_ciclo(app, id_admin)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.get(f"/ciclos/{id_ciclo}/editar")

    assert resposta.status_code == 403


# ----------------------------------------------------------------------
# Remarcar as próximas sessões
# ----------------------------------------------------------------------


def test_remarca_todas_as_sessoes_futuras(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo = montar_ciclo(app, id_fisio, sessoes=4)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    # Passa de segunda 09:00 para quarta 14:00.
    remarcar(client, id_ciclo, SEGUNDA, "14:00", ["2"])

    lista = sessoes_do_ciclo(app, id_ciclo)
    assert len(lista) == 4
    assert all(s.data.weekday() == 2 for s in lista)
    assert all(s.hora == time(14, 0) for s in lista)


def test_sessao_ja_realizada_nao_e_remarcada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo = montar_ciclo(app, id_fisio, sessoes=3, primeira=date(2026, 9, 21))

    with app.app_context():
        realizada = (
            Appointment.query.filter_by(ciclo_id=id_ciclo)
            .order_by(Appointment.data)
            .first()
        )
        realizada.status = "REALIZADO"
        db.session.commit()
        data_original = realizada.data

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    remarcar(client, id_ciclo, date(2026, 10, 7), "10:00", ["2"])

    lista = sessoes_do_ciclo(app, id_ciclo)
    assert lista[0].data == data_original
    assert lista[0].hora == time(9, 0)
    assert all(s.data.weekday() == 2 for s in lista[1:])


def test_sessao_no_passado_nao_e_remarcada(client, app, monkeypatch):
    """Sessão que ficou para trás sem baixa continua onde estava."""
    fixar_hoje(monkeypatch, date(2026, 10, 12))
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo = montar_ciclo(app, id_fisio, sessoes=3)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    remarcar(client, id_ciclo, date(2026, 10, 14), "11:00", ["2"])

    lista = sessoes_do_ciclo(app, id_ciclo)
    # 05/10 e 12/10 já passaram ou são hoje; só 19/10 muda.
    assert lista[0].data == SEGUNDA
    assert lista[0].hora == time(9, 0)


def test_remarcacao_pula_feriado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo = montar_ciclo(app, id_fisio, sessoes=2)

    quarta = date(2026, 10, 7)
    with app.app_context():
        db.session.add(Holiday(data=quarta, nome="Feriado municipal", tipo="MUNICIPAL"))
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    remarcar(client, id_ciclo, quarta, "10:00", ["2"])

    lista = sessoes_do_ciclo(app, id_ciclo)
    assert quarta not in [s.data for s in lista]
    assert lista[0].data == quarta + timedelta(days=7)


def test_remarcacao_respeita_o_limite_do_horario(client, app, monkeypatch):
    """Dois pacientes por horário é o teto; a remarcação não fura isso."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo = montar_ciclo(app, id_fisio, sessoes=2)

    quarta = date(2026, 10, 7)
    with app.app_context():
        outro = Patient(nome="Ja Ocupa", fisioterapeuta_id=id_fisio, ativo=True)
        db.session.add(outro)
        db.session.flush()
        for _ in range(2):
            db.session.add(
                Appointment(
                    tipo="SESSAO",
                    paciente_id=outro.id,
                    fisioterapeuta_id=id_fisio,
                    data=quarta,
                    hora=time(10, 0),
                    duracao_min=30,
                    status="AGENDADO",
                )
            )
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = remarcar(client, id_ciclo, quarta, "10:00", ["2"])

    assert "já está cheio" in resposta.get_data(as_text=True)
    assert sessoes_do_ciclo(app, id_ciclo)[0].data == SEGUNDA


def test_remarcar_para_o_mesmo_horario_nao_briga_consigo_mesmo(
    client, app, monkeypatch
):
    """As sessões que estão saindo não podem contar como ocupando o destino."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo = montar_ciclo(app, id_fisio, sessoes=3)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = remarcar(client, id_ciclo, SEGUNDA, "09:00", ["0"])

    assert "já está cheio" not in resposta.get_data(as_text=True)
    lista = sessoes_do_ciclo(app, id_ciclo)
    assert [s.data for s in lista] == [
        SEGUNDA,
        SEGUNDA + timedelta(days=7),
        SEGUNDA + timedelta(days=14),
    ]


def test_ciclo_encerrado_nao_remarca(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo = montar_ciclo(app, id_fisio, sessoes=2)

    with app.app_context():
        db.session.get(TreatmentCycle, id_ciclo).status = "ALTA"
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = remarcar(client, id_ciclo, date(2026, 10, 7), "10:00", ["2"])

    assert "ciclo ativo" in resposta.get_data(as_text=True)
    assert sessoes_do_ciclo(app, id_ciclo)[0].data == SEGUNDA


def test_sem_dia_da_semana_nao_remarca(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo = montar_ciclo(app, id_fisio, sessoes=2)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = remarcar(client, id_ciclo, date(2026, 10, 7), "10:00", [])

    assert "ao menos um dia da semana" in resposta.get_data(as_text=True)
    assert sessoes_do_ciclo(app, id_ciclo)[0].data == SEGUNDA


def test_tela_mostra_o_que_vai_mudar(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo = montar_ciclo(app, id_fisio, sessoes=3)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/ciclos/{id_ciclo}/remarcar").get_data(as_text=True)

    assert "05/10/2026" in pagina
    assert "19/10/2026" in pagina


def test_admin_tambem_remarca(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_ciclo = montar_ciclo(app, id_fisio, sessoes=2)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    remarcar(client, id_ciclo, date(2026, 10, 8), "13:30", ["3"])

    assert all(s.data.weekday() == 3 for s in sessoes_do_ciclo(app, id_ciclo))
