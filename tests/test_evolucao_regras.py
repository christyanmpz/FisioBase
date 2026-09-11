"""Regras de evolução clínica, status de agendamento e data de hoje.

Cobre as correções:
- o fisioterapeuta da sessão corrige evolução escrita por outra pessoa;
- quem tem acesso só ao paciente lê a evolução, sem editar;
- não há evolução em sessão futura, com falta ou cancelada;
- presença e falta só a partir do dia da sessão;
- "hoje" segue o fuso de São Paulo, não o do servidor.
"""

from datetime import date, datetime, time, timezone

import app as modulo_app
from conftest import SENHA_ADMIN, SENHA_FISIO, criar_usuario, fazer_login
from models import (
    PHYSIOTHERAPIST_PROFILE,
    Appointment,
    Evolution,
    Patient,
    TreatmentCycle,
    User,
    db,
)

DATA_PASSADA = date(2026, 9, 8)
DATA_FUTURA = date(2030, 1, 15)
SENHA_NOVA = "Nova@1234"


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def criar_fisioterapeuta(app, nome, email):
    with app.app_context():
        usuario = criar_usuario(nome, email, SENHA_NOVA, PHYSIOTHERAPIST_PROFILE)
        db.session.add(usuario)
        db.session.commit()
        return usuario.id


def criar_sessao(app, fisioterapeuta_id, status="AGENDADO", data=DATA_PASSADA):
    """Cria paciente, ciclo e uma sessão; devolve (paciente_id, agendamento_id)."""
    with app.app_context():
        paciente = Patient(
            nome="Josefa Prado", fisioterapeuta_id=fisioterapeuta_id, ativo=True
        )
        db.session.add(paciente)
        db.session.flush()

        ciclo = TreatmentCycle(
            paciente_id=paciente.id,
            fisioterapeuta_id=fisioterapeuta_id,
            regiao="JOELHO",
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
            hora=time(9, 0),
            duracao_min=30,
            numero_sessao=1,
            status=status,
        )
        db.session.add(agendamento)
        db.session.commit()
        return paciente.id, agendamento.id


def adicionar_sessao(app, paciente_id, status, data):
    """Acrescenta outra sessão ao mesmo paciente, no mesmo ciclo."""
    with app.app_context():
        primeira = db.session.scalar(
            db.select(Appointment).where(Appointment.paciente_id == paciente_id)
        )
        agendamento = Appointment(
            tipo="SESSAO",
            paciente_id=paciente_id,
            ciclo_id=primeira.ciclo_id,
            fisioterapeuta_id=primeira.fisioterapeuta_id,
            data=data,
            hora=time(10, 0),
            duracao_min=30,
            numero_sessao=1,
            status=status,
        )
        db.session.add(agendamento)
        db.session.commit()
        return agendamento.id


def registrar(client, agendamento_id, descricao="Mobilização de joelho."):
    return client.post(
        f"/agendamentos/{agendamento_id}/evolucao", data={"descricao": descricao}
    )


def contar_evolucoes(app):
    with app.app_context():
        return db.session.scalar(db.select(db.func.count(Evolution.id)))


def status_de(app, agendamento_id):
    with app.app_context():
        return db.session.get(Appointment, agendamento_id).status


def fixar_hoje(monkeypatch, dia):
    monkeypatch.setattr(modulo_app, "hoje", lambda: dia)


# ----------------------------------------------------------------------
# Quem edita e quem só lê
# ----------------------------------------------------------------------


def test_fisioterapeuta_da_sessao_corrige_evolucao_escrita_pelo_admin(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    registrar(client, id_agendamento, descricao="Escrito pelo admin.")
    client.post("/logout")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    tela = client.get(f"/agendamentos/{id_agendamento}/evolucao")
    assert tela.status_code == 200
    assert 'name="descricao"' in tela.get_data(as_text=True)

    resposta = registrar(client, id_agendamento, descricao="Corrigido pela fisio.")
    assert resposta.status_code == 302
    with app.app_context():
        assert db.session.scalar(db.select(Evolution)).descricao == (
            "Corrigido pela fisio."
        )


def test_novo_responsavel_do_paciente_le_evolucao_sem_editar(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente, id_agendamento = criar_sessao(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    registrar(client, id_agendamento, descricao="Texto original da fisio.")
    client.post("/logout")

    id_nova = criar_fisioterapeuta(app, "Nova Responsavel", "nova@teste.com")
    with app.app_context():
        db.session.get(Patient, id_paciente).fisioterapeuta_id = id_nova
        db.session.commit()

    fazer_login(client, "nova@teste.com", SENHA_NOVA)
    tela = client.get(f"/agendamentos/{id_agendamento}/evolucao")
    corpo = tela.get_data(as_text=True)
    assert tela.status_code == 200
    assert "Texto original da fisio." in corpo
    assert 'name="descricao"' not in corpo

    assert registrar(client, id_agendamento, descricao="Alterado").status_code == 403
    with app.app_context():
        assert db.session.scalar(db.select(Evolution)).descricao == (
            "Texto original da fisio."
        )


def test_novo_responsavel_nao_registra_evolucao_em_sessao_de_outro(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente, id_agendamento = criar_sessao(app, id_fisio, status="REALIZADO")

    id_nova = criar_fisioterapeuta(app, "Nova Responsavel", "nova@teste.com")
    with app.app_context():
        db.session.get(Patient, id_paciente).fisioterapeuta_id = id_nova
        db.session.commit()

    fazer_login(client, "nova@teste.com", SENHA_NOVA)
    assert client.get(f"/agendamentos/{id_agendamento}/evolucao").status_code == 403
    assert registrar(client, id_agendamento).status_code == 403
    assert contar_evolucoes(app) == 0


# ----------------------------------------------------------------------
# Em quais sessões a evolução é permitida
# ----------------------------------------------------------------------


def test_evolucao_em_sessao_com_falta_e_recusada(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio, status="FALTOU")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    registrar(client, id_agendamento)

    assert contar_evolucoes(app) == 0
    assert status_de(app, id_agendamento) == "FALTOU"


def test_evolucao_em_sessao_cancelada_e_recusada(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio, status="CANCELADO")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    registrar(client, id_agendamento)

    assert contar_evolucoes(app) == 0
    assert status_de(app, id_agendamento) == "CANCELADO"


def test_evolucao_em_sessao_futura_e_recusada_e_status_nao_muda(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio, data=DATA_FUTURA)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    registrar(client, id_agendamento)

    assert contar_evolucoes(app) == 0
    assert status_de(app, id_agendamento) == "AGENDADO"


def test_evolucao_no_proprio_dia_da_sessao_e_aceita(client, app, monkeypatch):
    fixar_hoje(monkeypatch, DATA_FUTURA)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio, data=DATA_FUTURA)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    registrar(client, id_agendamento)

    assert contar_evolucoes(app) == 1
    assert status_de(app, id_agendamento) == "REALIZADO"


def test_evolucao_existente_em_sessao_que_virou_falta_fica_so_leitura(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    registrar(client, id_agendamento, descricao="Registrada antes da falta.")
    with app.app_context():
        db.session.get(Appointment, id_agendamento).status = "FALTOU"
        db.session.commit()

    corpo = client.get(f"/agendamentos/{id_agendamento}/evolucao").get_data(
        as_text=True
    )
    assert "Registrada antes da falta." in corpo
    assert 'name="descricao"' not in corpo

    registrar(client, id_agendamento, descricao="Tentativa de edição.")
    with app.app_context():
        assert db.session.scalar(db.select(Evolution)).descricao == (
            "Registrada antes da falta."
        )


def test_ficha_so_oferece_registrar_onde_e_permitido(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente, id_permitida = criar_sessao(app, id_fisio, status="REALIZADO")
    id_falta = adicionar_sessao(app, id_paciente, "FALTOU", DATA_PASSADA)
    id_futura = adicionar_sessao(app, id_paciente, "AGENDADO", DATA_FUTURA)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get(f"/pacientes/{id_paciente}").get_data(as_text=True)

    assert f"/agendamentos/{id_permitida}/evolucao" in corpo
    assert f"/agendamentos/{id_falta}/evolucao" not in corpo
    assert f"/agendamentos/{id_futura}/evolucao" not in corpo


# ----------------------------------------------------------------------
# Presença e falta só a partir do dia da sessão
# ----------------------------------------------------------------------


def test_marcar_realizado_em_data_futura_e_recusado(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio, data=DATA_FUTURA)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    client.post(f"/agendamentos/{id_agendamento}/status", data={"status": "REALIZADO"})

    assert status_de(app, id_agendamento) == "AGENDADO"


def test_marcar_falta_em_data_futura_e_recusado(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio, data=DATA_FUTURA)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    client.post(f"/agendamentos/{id_agendamento}/status", data={"status": "FALTOU"})

    assert status_de(app, id_agendamento) == "AGENDADO"


def test_marcar_realizado_no_dia_da_sessao_e_aceito(client, app, monkeypatch):
    fixar_hoje(monkeypatch, DATA_FUTURA)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio, data=DATA_FUTURA)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    client.post(f"/agendamentos/{id_agendamento}/status", data={"status": "REALIZADO"})

    assert status_de(app, id_agendamento) == "REALIZADO"


def test_cancelar_ou_confirmar_sessao_futura_continua_permitido(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio, data=DATA_FUTURA)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    client.post(f"/agendamentos/{id_agendamento}/status", data={"status": "CONFIRMADO"})
    assert status_de(app, id_agendamento) == "CONFIRMADO"

    client.post(f"/agendamentos/{id_agendamento}/status", data={"status": "CANCELADO"})
    assert status_de(app, id_agendamento) == "CANCELADO"


# ----------------------------------------------------------------------
# Data de hoje no fuso de São Paulo
# ----------------------------------------------------------------------


def test_hoje_usa_o_fuso_de_sao_paulo():
    # 01:30 de 12/09 em UTC ainda são 22:30 de 11/09 em São Paulo.
    noite_em_utc = datetime(2026, 9, 12, 1, 30, tzinfo=timezone.utc)
    assert modulo_app.hoje(noite_em_utc) == date(2026, 9, 11)


def test_agenda_sem_data_abre_no_hoje_de_sao_paulo(client, app, monkeypatch):
    fixar_hoje(monkeypatch, DATA_FUTURA)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_sessao(app, id_fisio, data=DATA_FUTURA)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/agenda").get_data(as_text=True)

    assert "Josefa Prado" in corpo
