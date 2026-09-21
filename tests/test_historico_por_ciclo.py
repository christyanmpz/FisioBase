"""Histórico do paciente agrupado por ciclo de tratamento.

Misturados por data, os atendimentos de tratamentos antigos se confundem
com os do atual. A clínica pediu o ciclo em andamento primeiro e os
encerrados por último, na ficha e no prontuário impresso.
"""

from datetime import date, time, timedelta

import app as modulo_app
from conftest import SENHA_FISIO, fazer_login
from models import Appointment, Patient, TreatmentCycle, User, db

HOJE = date(2026, 9, 14)


def fixar_hoje(monkeypatch, dia=HOJE):
    monkeypatch.setattr(modulo_app, "hoje", lambda: dia)


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def montar_paciente(app, id_fisio):
    """Um paciente com três ciclos: dois encerrados e um em andamento."""
    with app.app_context():
        paciente = Patient(
            nome="Dirceu Nogueira", fisioterapeuta_id=id_fisio, ativo=True
        )
        db.session.add(paciente)
        db.session.flush()

        for regiao, avaliacao, status in [
            ("OMBRO", date(2024, 3, 4), "ALTA"),
            ("JOELHO", date(2025, 6, 2), "ALTA"),
            ("COLUNA", date(2026, 8, 3), "ATIVO"),
        ]:
            ciclo = TreatmentCycle(
                paciente_id=paciente.id,
                fisioterapeuta_id=id_fisio,
                regiao=regiao,
                modalidade="INDIVIDUAL",
                data_avaliacao=avaliacao,
                total_sessoes=10,
                status=status,
            )
            db.session.add(ciclo)
            db.session.flush()

            for n in range(2):
                db.session.add(
                    Appointment(
                        tipo="SESSAO",
                        paciente_id=paciente.id,
                        ciclo_id=ciclo.id,
                        fisioterapeuta_id=id_fisio,
                        data=avaliacao + timedelta(days=7 * (n + 1)),
                        hora=time(9, 0),
                        duracao_min=30,
                        status="REALIZADO",
                        numero_sessao=n + 1,
                    )
                )

        db.session.commit()
        return paciente.id


def posicoes(pagina, *textos):
    return [pagina.index(t) for t in textos]


def test_ficha_traz_o_ciclo_ativo_primeiro(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = montar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/pacientes/{id_paciente}").get_data(as_text=True)

    coluna, joelho, ombro = posicoes(pagina, "Coluna", "Joelho", "Ombro")
    assert coluna < joelho < ombro


def test_ficha_marca_o_ciclo_em_tratamento(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = montar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/pacientes/{id_paciente}").get_data(as_text=True)

    assert "Em tratamento" in pagina
    assert "avaliação em 03/08/2026" in pagina


def test_sessoes_ficam_na_ordem_em_que_aconteceram(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = montar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/pacientes/{id_paciente}").get_data(as_text=True)

    primeira, segunda = posicoes(pagina, "10/08/2026", "17/08/2026")
    assert primeira < segunda


def test_prontuario_segue_a_mesma_ordem(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = montar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/pacientes/{id_paciente}/prontuario").get_data(as_text=True)

    coluna, joelho, ombro = posicoes(
        pagina,
        "Tratamento de Coluna",
        "Tratamento de Joelho",
        "Tratamento de Ombro",
    )
    assert coluna < joelho < ombro


def test_atendimento_sem_ciclo_vai_para_o_fim(client, app, monkeypatch):
    """Triagem avulsa não pertence a ciclo nenhum, mas não pode sumir."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = montar_paciente(app, id_fisio)

    with app.app_context():
        db.session.add(
            Appointment(
                tipo="AVALIACAO",
                paciente_id=id_paciente,
                fisioterapeuta_id=id_fisio,
                data=date(2026, 9, 2),
                hora=time(8, 0),
                duracao_min=30,
                status="REALIZADO",
            )
        )
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/pacientes/{id_paciente}").get_data(as_text=True)

    fora, ombro = posicoes(pagina, "Atendimentos fora de ciclo", "Ombro")
    assert ombro < fora
    assert "02/09/2026" in pagina


def test_paciente_sem_atendimento_mostra_o_estado_vazio(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    with app.app_context():
        paciente = Patient(nome="Recem Cadastrado", fisioterapeuta_id=id_fisio)
        paciente.ativo = True
        db.session.add(paciente)
        db.session.commit()
        id_paciente = paciente.id

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get(f"/pacientes/{id_paciente}").get_data(as_text=True)

    assert "Nenhum atendimento registrado" in pagina
