"""Geração automática das sessões do ciclo e cartão do paciente."""

from datetime import date, time, timedelta

import app as modulo_app
from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from models import Appointment, Card, Holiday, Patient, TreatmentCycle, User, db

SEGUNDA = date(2026, 10, 5)


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def fixar_hoje(monkeypatch, dia=SEGUNDA - timedelta(days=7)):
    monkeypatch.setattr(modulo_app, "hoje", lambda: dia)


def montar_ciclo(app, fisioterapeuta_id, total=10, status="ATIVO"):
    with app.app_context():
        paciente = Patient(
            nome="Marta Figueiredo", fisioterapeuta_id=fisioterapeuta_id, ativo=True
        )
        db.session.add(paciente)
        db.session.flush()

        ciclo = TreatmentCycle(
            paciente_id=paciente.id,
            fisioterapeuta_id=fisioterapeuta_id,
            regiao="JOELHO",
            modalidade="INDIVIDUAL",
            data_avaliacao=date(2026, 10, 1),
            total_sessoes=total,
            status=status,
        )
        db.session.add(ciclo)
        db.session.commit()
        return paciente.id, ciclo.id


def gerar(client, ciclo_id, **campos):
    dados = {
        "inicio": SEGUNDA.isoformat(),
        "hora": "09:00",
        "dias": ["0", "2"],
        "quantidade": "10",
    }
    dados.update(campos)
    return client.post(f"/ciclos/{ciclo_id}/sessoes", data=dados)


def sessoes(app, ciclo_id):
    with app.app_context():
        return (
            Appointment.query.filter_by(ciclo_id=ciclo_id)
            .order_by(Appointment.data)
            .all()
        )


def cadastrar_feriado(app, dia, nome="Feriado municipal"):
    with app.app_context():
        db.session.add(Holiday(data=dia, nome=nome, tipo="MUNICIPAL"))
        db.session.commit()


# ----------------------------------------------------------------------
# Geração das sessões
# ----------------------------------------------------------------------


def test_gera_as_sessoes_nos_dias_escolhidos(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_ciclo = montar_ciclo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    assert gerar(client, id_ciclo).status_code == 302

    lista = sessoes(app, id_ciclo)
    assert len(lista) == 10
    assert all(s.hora == time(9, 0) for s in lista)
    assert all(s.data.weekday() in (0, 2) for s in lista)
    assert lista[0].data == SEGUNDA
    assert lista[1].data == SEGUNDA + timedelta(days=2)


def test_uma_vez_por_semana_espaca_de_sete_em_sete(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_ciclo = montar_ciclo(app, id_fisio, total=4)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_ciclo, dias=["0"], quantidade="4")

    lista = sessoes(app, id_ciclo)
    assert [s.data for s in lista] == [
        SEGUNDA + timedelta(days=7 * n) for n in range(4)
    ]


def test_feriado_e_pulado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_ciclo = montar_ciclo(app, id_fisio, total=3)
    cadastrar_feriado(app, SEGUNDA + timedelta(days=7), "Aniversário da cidade")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_ciclo, dias=["0"], quantidade="3")

    datas = [s.data for s in sessoes(app, id_ciclo)]
    assert SEGUNDA + timedelta(days=7) not in datas
    assert len(datas) == 3
    assert datas[-1] == SEGUNDA + timedelta(days=21)


def test_nao_gera_alem_do_total_do_ciclo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_ciclo = montar_ciclo(app, id_fisio, total=4)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = gerar(client, id_ciclo, quantidade="10")

    assert resposta.status_code == 400
    assert sessoes(app, id_ciclo) == []


def test_segunda_geracao_respeita_o_que_ja_existe(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_ciclo = montar_ciclo(app, id_fisio, total=10)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_ciclo, dias=["0"], quantidade="6")
    corpo = client.get(f"/ciclos/{id_ciclo}/sessoes").get_data(as_text=True)

    assert "6" in corpo
    gerar(client, id_ciclo, dias=["2"], quantidade="4", hora="10:00")
    assert len(sessoes(app, id_ciclo)) == 10


def test_data_no_passado_e_recusada(client, app, monkeypatch):
    fixar_hoje(monkeypatch, SEGUNDA + timedelta(days=30))
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_ciclo = montar_ciclo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = gerar(client, id_ciclo)

    assert resposta.status_code == 400
    assert sessoes(app, id_ciclo) == []


def test_sem_dia_da_semana_e_recusado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_ciclo = montar_ciclo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = gerar(client, id_ciclo, dias=[])

    assert resposta.status_code == 400
    assert sessoes(app, id_ciclo) == []


def test_fim_de_semana_e_recusado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_ciclo = montar_ciclo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = gerar(client, id_ciclo, dias=["5"])

    assert resposta.status_code == 400
    assert sessoes(app, id_ciclo) == []


def test_horario_fora_da_grade_e_recusado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_ciclo = montar_ciclo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = gerar(client, id_ciclo, hora="12:00")

    assert resposta.status_code == 400
    assert sessoes(app, id_ciclo) == []


def test_horario_cheio_e_recusado_sem_gravar_nada(client, app, monkeypatch):
    """O limite de 2 por horário vale também na geração em lote."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente, id_ciclo = montar_ciclo(app, id_fisio)

    with app.app_context():
        for _ in range(2):
            db.session.add(
                Appointment(
                    tipo="SESSAO",
                    paciente_id=id_paciente,
                    fisioterapeuta_id=id_fisio,
                    data=SEGUNDA,
                    hora=time(9, 0),
                    duracao_min=30,
                    status="AGENDADO",
                )
            )
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = gerar(client, id_ciclo)

    assert resposta.status_code == 400
    assert sessoes(app, id_ciclo) == []


def test_ciclo_encerrado_nao_gera(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_ciclo = montar_ciclo(app, id_fisio, status="ALTA")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = gerar(client, id_ciclo)

    assert resposta.status_code == 400
    assert sessoes(app, id_ciclo) == []


def test_outro_fisioterapeuta_nao_gera(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_admin = id_do_usuario(app, "admin@teste.com")
    _, id_ciclo = montar_ciclo(app, id_admin)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert client.get(f"/ciclos/{id_ciclo}/sessoes").status_code == 403
    assert gerar(client, id_ciclo).status_code == 403


# ----------------------------------------------------------------------
# Cartão do paciente
# ----------------------------------------------------------------------


def test_cartao_lista_as_datas_numeradas(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_ciclo = montar_ciclo(app, id_fisio, total=3)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_ciclo, dias=["0"], quantidade="3")
    corpo = client.get(f"/ciclos/{id_ciclo}/cartao").get_data(as_text=True)

    assert "Cartão de atendimento" in corpo
    assert "Marta Figueiredo" in corpo
    assert SEGUNDA.strftime("%d/%m/%Y") in corpo
    assert "09:00" in corpo


def test_cartao_registra_a_emissao_uma_vez(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_ciclo = montar_ciclo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    client.get(f"/ciclos/{id_ciclo}/cartao")
    client.get(f"/ciclos/{id_ciclo}/cartao")

    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Card.id))) == 1


def test_cartao_sem_sessoes_nao_quebra(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_ciclo = montar_ciclo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.get(f"/ciclos/{id_ciclo}/cartao")

    assert resposta.status_code == 200
    assert "Nenhuma sessão agendada" in resposta.get_data(as_text=True)


def test_cartao_nao_lista_sessao_cancelada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    _, id_ciclo = montar_ciclo(app, id_fisio, total=2)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_ciclo, dias=["0"], quantidade="2")
    with app.app_context():
        primeira = db.session.scalar(
            db.select(Appointment).where(Appointment.ciclo_id == id_ciclo)
        )
        primeira.status = "CANCELADO"
        db.session.commit()

    corpo = client.get(f"/ciclos/{id_ciclo}/cartao").get_data(as_text=True)

    assert SEGUNDA.strftime("%d/%m/%Y") not in corpo


def test_outro_fisioterapeuta_nao_abre_o_cartao(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_admin = id_do_usuario(app, "admin@teste.com")
    _, id_ciclo = montar_ciclo(app, id_admin)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert client.get(f"/ciclos/{id_ciclo}/cartao").status_code == 403


def test_lista_de_ciclos_oferece_os_botoes(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente, id_ciclo = montar_ciclo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get(f"/pacientes/{id_paciente}/ciclos").get_data(as_text=True)

    assert f"/ciclos/{id_ciclo}/sessoes" in corpo
    assert f"/ciclos/{id_ciclo}/cartao" in corpo
