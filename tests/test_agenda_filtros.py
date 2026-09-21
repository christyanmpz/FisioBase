"""O que a agenda mostra e o que ela esconde.

Duas regras pedidas pela clínica: a agenda do dia é de quem está em
tratamento — sessão de ciclo encerrado sai dali e fica só no prontuário —
e a grade semanal não pode abrir vazia escondendo atendimento que existe.
"""

from datetime import date, time, timedelta

import app as modulo_app
from conftest import SENHA_ADMIN, SENHA_FISIO, criar_usuario, fazer_login
from models import (
    PHYSIOTHERAPIST_PROFILE,
    Appointment,
    Patient,
    TreatmentCycle,
    User,
    db,
)

# 05/10/2026 é uma segunda-feira.
SEGUNDA = date(2026, 10, 5)


def fixar_hoje(monkeypatch, dia=SEGUNDA):
    monkeypatch.setattr(modulo_app, "hoje", lambda: dia)


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def montar(app, fisioterapeuta_id, status_do_ciclo, nome, dia=SEGUNDA, hora=time(9, 0)):
    """Cria paciente, ciclo no status pedido e uma sessão nesse ciclo."""
    with app.app_context():
        paciente = Patient(nome=nome, fisioterapeuta_id=fisioterapeuta_id, ativo=True)
        db.session.add(paciente)
        db.session.flush()

        ciclo = TreatmentCycle(
            paciente_id=paciente.id,
            fisioterapeuta_id=fisioterapeuta_id,
            regiao="OMBRO",
            modalidade="INDIVIDUAL",
            data_avaliacao=date(2026, 9, 1),
            total_sessoes=10,
            status=status_do_ciclo,
        )
        db.session.add(ciclo)
        db.session.flush()

        db.session.add(
            Appointment(
                tipo="SESSAO",
                paciente_id=paciente.id,
                ciclo_id=ciclo.id,
                fisioterapeuta_id=fisioterapeuta_id,
                data=dia,
                hora=hora,
                duracao_min=30,
                status="AGENDADO",
            )
        )
        db.session.commit()


# ----------------------------------------------------------------------
# Ciclo encerrado sai da agenda
# ----------------------------------------------------------------------


def test_agenda_do_dia_esconde_sessao_de_ciclo_encerrado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    montar(app, id_fisio, "ATIVO", "Em Tratamento")
    montar(app, id_fisio, "ALTA", "Ja Recebeu Alta", hora=time(9, 30))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/agenda?data={SEGUNDA.isoformat()}").get_data(as_text=True)

    assert "Em Tratamento" in pagina
    assert "Ja Recebeu Alta" not in pagina


def test_grade_do_dia_esconde_sessao_de_ciclo_encerrado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    montar(app, id_fisio, "ATIVO", "Em Tratamento")
    montar(app, id_fisio, "ABANDONO", "Abandonou O Ciclo", hora=time(9, 30))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/agenda/dia?data={SEGUNDA.isoformat()}").get_data(
        as_text=True
    )

    assert "Em Tratamento" in pagina
    assert "Abandonou O Ciclo" not in pagina


def test_grade_semanal_esconde_sessao_de_ciclo_encerrado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    montar(app, id_fisio, "ATIVO", "Em Tratamento")
    montar(app, id_fisio, "ALTA", "Ja Recebeu Alta", hora=time(9, 30))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/agenda/semana?data={SEGUNDA.isoformat()}").get_data(
        as_text=True
    )

    assert "Em Tratamento" in pagina
    assert "Ja Recebeu Alta" not in pagina


def test_avaliacao_sem_ciclo_continua_na_agenda(client, app, monkeypatch):
    """Triagem não tem ciclo: o filtro não pode derrubá-la junto."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    with app.app_context():
        paciente = Patient(nome="Vem Pra Triagem", fisioterapeuta_id=id_fisio)
        paciente.ativo = True
        db.session.add(paciente)
        db.session.flush()
        db.session.add(
            Appointment(
                tipo="AVALIACAO",
                paciente_id=paciente.id,
                fisioterapeuta_id=id_fisio,
                data=SEGUNDA,
                hora=time(8, 0),
                duracao_min=30,
                status="AGENDADO",
            )
        )
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/agenda?data={SEGUNDA.isoformat()}").get_data(as_text=True)

    assert "Vem Pra Triagem" in pagina


# ----------------------------------------------------------------------
# A grade semanal não abre vazia
# ----------------------------------------------------------------------


def criar_segundo_fisio(app, nome="Ana Prado"):
    """Fica antes de 'Rafael Santos' na ordem alfabética da lista."""
    with app.app_context():
        usuario = criar_usuario(
            nome, "ana@teste.com", "Fisio@123", PHYSIOTHERAPIST_PROFILE
        )
        db.session.add(usuario)
        db.session.commit()
        return usuario.id


def test_admin_abre_a_grade_em_quem_tem_atendimento_na_semana(client, app, monkeypatch):
    """Antes abria sempre no primeiro em ordem alfabética, e a semana
    aparecia vazia mesmo havendo agendamento na clínica."""
    fixar_hoje(monkeypatch)
    criar_segundo_fisio(app)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    montar(app, id_fisio, "ATIVO", "Tem Sessao")

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    pagina = client.get(f"/agenda/semana?data={SEGUNDA.isoformat()}").get_data(
        as_text=True
    )

    assert "Tem Sessao" in pagina
    assert "Rafael Santos" in pagina


def test_admin_respeita_o_profissional_escolhido(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_ana = criar_segundo_fisio(app)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    montar(app, id_fisio, "ATIVO", "Tem Sessao")

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    pagina = client.get(
        f"/agenda/semana?data={SEGUNDA.isoformat()}&fisioterapeuta_id={id_ana}"
    ).get_data(as_text=True)

    assert "Ana Prado" in pagina
    assert "Tem Sessao" not in pagina


def test_filtro_com_valor_invalido_nao_quebra(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    resposta = client.get(f"/agenda/semana?fisioterapeuta_id=abc")

    assert resposta.status_code == 200


def test_grade_mostra_horario_fora_do_expediente(client, app, monkeypatch):
    """Agendamento antigo, de antes da grade atual, não pode sumir da tela."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    montar(app, id_fisio, "ATIVO", "Horario Antigo", hora=time(16, 30))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/agenda/semana?data={SEGUNDA.isoformat()}").get_data(
        as_text=True
    )

    assert "Horario Antigo" in pagina
    assert "16:30" in pagina


def test_grade_mantem_a_ordem_dos_horarios(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    montar(app, id_fisio, "ATIVO", "Cedinho", hora=time(7, 0))
    montar(
        app,
        id_fisio,
        "ATIVO",
        "Fim Do Dia",
        dia=SEGUNDA + timedelta(days=1),
        hora=time(16, 30),
    )

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/agenda/semana?data={SEGUNDA.isoformat()}").get_data(
        as_text=True
    )

    assert pagina.index("07:00") < pagina.index("07:30")
    assert pagina.index("15:30") < pagina.index("16:30")
