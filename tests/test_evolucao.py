"""Testes da evolução clínica.

Estes testes registram o comportamento que JÁ funciona e deve continuar
funcionando depois das correções do fluxo de evolução. Todos usam datas no
passado, para continuarem válidos quando o sistema passar a recusar
evolução em sessão futura.
"""

from datetime import date, time

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

DATA_SESSAO = date(2026, 9, 8)


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def criar_sessao(app, fisioterapeuta_id, status="AGENDADO"):
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
            data=DATA_SESSAO,
            hora=time(9, 0),
            duracao_min=30,
            numero_sessao=1,
            status=status,
        )
        db.session.add(agendamento)
        db.session.commit()
        return paciente.id, agendamento.id


def registrar(client, agendamento_id, **campos):
    dados = {
        "descricao": "Fortalecimento de quadríceps, 3x12.",
        "evolucao": "Dor 4/10, melhora da amplitude.",
        "observacoes": "Gelo em casa.",
    }
    dados.update(campos)
    return client.post(f"/agendamentos/{agendamento_id}/evolucao", data=dados)


def contar_evolucoes(app):
    with app.app_context():
        return db.session.scalar(db.select(db.func.count(Evolution.id)))


def test_registrar_evolucao_grava_e_marca_realizado(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente, id_agendamento = criar_sessao(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = registrar(client, id_agendamento)

    assert resposta.status_code == 302
    with app.app_context():
        evolucao = db.session.scalar(db.select(Evolution))
        assert evolucao.agendamento_id == id_agendamento
        assert evolucao.paciente_id == id_paciente
        assert evolucao.fisioterapeuta_id == id_fisio
        assert evolucao.data == DATA_SESSAO
        assert evolucao.descricao == "Fortalecimento de quadríceps, 3x12."
        assert evolucao.evolucao == "Dor 4/10, melhora da amplitude."
        assert evolucao.observacoes == "Gelo em casa."
        assert db.session.get(Appointment, id_agendamento).status == "REALIZADO"


def test_evolucao_em_sessao_ja_marcada_como_realizada_pela_recepcao(client, app):
    """Cenário relatado pela clínica: a recepção marca presença, o
    fisioterapeuta escreve a evolução depois."""
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    client.post(f"/agendamentos/{id_agendamento}/status", data={"status": "REALIZADO"})
    client.post("/logout")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    assert client.get(f"/agendamentos/{id_agendamento}/evolucao").status_code == 200
    resposta = registrar(client, id_agendamento)

    assert resposta.status_code == 302
    assert contar_evolucoes(app) == 1
    with app.app_context():
        assert db.session.get(Appointment, id_agendamento).status == "REALIZADO"


def test_ficha_oferece_registrar_evolucao_em_sessao_realizada(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente, id_agendamento = criar_sessao(app, id_fisio, status="REALIZADO")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get(f"/pacientes/{id_paciente}").get_data(as_text=True)

    assert f"/agendamentos/{id_agendamento}/evolucao" in corpo
    assert "Registrar" in corpo


def test_salvar_de_novo_edita_sem_duplicar(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    registrar(client, id_agendamento)
    registrar(client, id_agendamento, descricao="Texto corrigido.")

    assert contar_evolucoes(app) == 1
    with app.app_context():
        assert db.session.scalar(db.select(Evolution)).descricao == "Texto corrigido."


def test_descricao_e_obrigatoria(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = registrar(client, id_agendamento, descricao="   ")

    assert resposta.status_code == 400
    assert contar_evolucoes(app) == 0
    with app.app_context():
        assert db.session.get(Appointment, id_agendamento).status == "AGENDADO"


def test_admin_corrige_evolucao_e_autoria_e_mantida(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    registrar(client, id_agendamento)
    client.post("/logout")

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    resposta = registrar(client, id_agendamento, descricao="Corrigido pelo admin.")

    assert resposta.status_code == 302
    with app.app_context():
        evolucao = db.session.scalar(db.select(Evolution))
        assert evolucao.descricao == "Corrigido pelo admin."
        assert evolucao.fisioterapeuta_id == id_fisio


def test_outro_fisioterapeuta_nao_acessa_evolucao(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio)

    with app.app_context():
        db.session.add(
            criar_usuario(
                "Outra Fisio", "outra@teste.com", SENHA_FISIO, PHYSIOTHERAPIST_PROFILE
            )
        )
        db.session.commit()

    fazer_login(client, "outra@teste.com", SENHA_FISIO)

    assert client.get(f"/agendamentos/{id_agendamento}/evolucao").status_code == 403
    assert registrar(client, id_agendamento).status_code == 403
    assert contar_evolucoes(app) == 0


def test_evolucao_de_agendamento_inexistente(client):
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    assert client.get("/agendamentos/9999/evolucao").status_code == 404


def test_evolucao_exige_login(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_agendamento = criar_sessao(app, id_fisio)

    resposta = client.get(f"/agendamentos/{id_agendamento}/evolucao")

    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]
