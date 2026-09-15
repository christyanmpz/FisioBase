"""Impressão do prontuário completo e da folha de evolução."""

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

SENHA_NOVA = "Nova@1234"
DATA_SESSAO = date(2026, 9, 8)


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def montar_paciente(app, fisioterapeuta_id, nome="Dirceu Almeida Pinto"):
    """Cria paciente, ciclo e uma sessão realizada; devolve os três ids."""
    with app.app_context():
        paciente = Patient(
            nome=nome,
            cpf="52601815906",
            data_nascimento=date(1958, 3, 11),
            telefone="(19) 99812-4477",
            cid="M75.1",
            diagnostico="Tendinopatia do manguito rotador à direita",
            fisioterapeuta_id=fisioterapeuta_id,
            ativo=True,
        )
        db.session.add(paciente)
        db.session.flush()

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
            data=DATA_SESSAO,
            hora=time(9, 0),
            duracao_min=30,
            numero_sessao=1,
            status="REALIZADO",
        )
        db.session.add(agendamento)
        db.session.commit()
        return paciente.id, ciclo.id, agendamento.id


def escrever_evolucao(app, agendamento_id, fisioterapeuta_id):
    with app.app_context():
        agendamento = db.session.get(Appointment, agendamento_id)
        db.session.add(
            Evolution(
                ciclo_id=agendamento.ciclo_id,
                paciente_id=agendamento.paciente_id,
                agendamento_id=agendamento.id,
                fisioterapeuta_id=fisioterapeuta_id,
                data=agendamento.data,
                descricao="Mobilização escapular e fortalecimento de rotadores.",
                evolucao="Refere melhora da dor noturna.",
                observacoes="Manter exercícios em casa.",
            )
        )
        db.session.commit()


# ----------------------------------------------------------------------
# Prontuário completo
# ----------------------------------------------------------------------


def test_prontuario_reune_cadastro_ciclo_e_evolucoes(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente, _, id_agendamento = montar_paciente(app, id_fisio)
    escrever_evolucao(app, id_agendamento, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get(f"/pacientes/{id_paciente}/prontuario").get_data(as_text=True)

    assert "Dirceu Almeida Pinto" in corpo
    assert "52601815906" in corpo
    assert "M75.1" in corpo
    assert "Tendinopatia do manguito rotador à direita" in corpo
    assert "Mobilização escapular e fortalecimento de rotadores." in corpo
    assert "Refere melhora da dor noturna." in corpo
    assert "Assinatura e carimbo do profissional" in corpo


def test_prontuario_aponta_sessao_realizada_sem_evolucao(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente, _, _ = montar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get(f"/pacientes/{id_paciente}/prontuario").get_data(as_text=True)

    assert "Evolução não registrada." in corpo


def test_prontuario_nao_lista_cancelados(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente, id_ciclo, _ = montar_paciente(app, id_fisio)
    with app.app_context():
        db.session.add(
            Appointment(
                tipo="SESSAO",
                paciente_id=id_paciente,
                ciclo_id=id_ciclo,
                fisioterapeuta_id=id_fisio,
                data=DATA_SESSAO,
                hora=time(14, 0),
                duracao_min=30,
                status="CANCELADO",
            )
        )
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get(f"/pacientes/{id_paciente}/prontuario").get_data(as_text=True)

    assert "14:00" not in corpo


def test_ficha_oferece_o_botao_de_prontuario(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente, _, _ = montar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get(f"/pacientes/{id_paciente}").get_data(as_text=True)

    assert f"/pacientes/{id_paciente}/prontuario" in corpo


def test_outro_fisioterapeuta_nao_abre_o_prontuario(client, app):
    id_admin = id_do_usuario(app, "admin@teste.com")
    id_paciente, _, _ = montar_paciente(app, id_admin)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert client.get(f"/pacientes/{id_paciente}/prontuario").status_code == 403


def test_prontuario_de_paciente_inexistente(client):
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert client.get("/pacientes/9999/prontuario").status_code == 404


def test_prontuario_exige_login(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente, _, _ = montar_paciente(app, id_fisio)

    resposta = client.get(f"/pacientes/{id_paciente}/prontuario")

    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


# ----------------------------------------------------------------------
# Folha da sessão
# ----------------------------------------------------------------------


def test_folha_da_sessao_sai_com_a_evolucao(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, _, id_agendamento = montar_paciente(app, id_fisio)
    escrever_evolucao(app, id_agendamento, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get(f"/agendamentos/{id_agendamento}/evolucao").get_data(
        as_text=True
    )

    assert "folha print-only" in corpo
    assert "Evolução clínica" in corpo
    assert "Dirceu Almeida Pinto" in corpo
    assert "Refere melhora da dor noturna." in corpo


def test_sessao_sem_evolucao_nao_tem_folha(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, _, id_agendamento = montar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get(f"/agendamentos/{id_agendamento}/evolucao").get_data(
        as_text=True
    )

    assert "folha print-only" not in corpo


def test_folha_sai_tambem_no_modo_somente_leitura(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente, _, id_agendamento = montar_paciente(app, id_fisio)
    escrever_evolucao(app, id_agendamento, id_fisio)

    with app.app_context():
        db.session.add(
            criar_usuario(
                "Nova Fisio", "nova@teste.com", SENHA_NOVA, PHYSIOTHERAPIST_PROFILE
            )
        )
        db.session.commit()
    id_nova = id_do_usuario(app, "nova@teste.com")
    with app.app_context():
        db.session.get(Patient, id_paciente).fisioterapeuta_id = id_nova
        db.session.commit()

    fazer_login(client, "nova@teste.com", SENHA_NOVA)
    corpo = client.get(f"/agendamentos/{id_agendamento}/evolucao").get_data(
        as_text=True
    )

    assert "folha print-only" in corpo
    assert "Refere melhora da dor noturna." in corpo
