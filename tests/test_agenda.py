"""Testes da agenda e da validação de CPF."""

from datetime import date

from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from models import Appointment, Patient, TreatmentCycle, User, db


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def criar_paciente(app, nome, fisioterapeuta_id):
    with app.app_context():
        paciente = Patient(nome=nome, fisioterapeuta_id=fisioterapeuta_id, ativo=True)
        db.session.add(paciente)
        db.session.commit()
        return paciente.id


def criar_ciclo(app, paciente_id, fisioterapeuta_id):
    with app.app_context():
        ciclo = TreatmentCycle(
            paciente_id=paciente_id,
            fisioterapeuta_id=fisioterapeuta_id,
            regiao="JOELHO",
            modalidade="INDIVIDUAL",
            data_avaliacao=date(2026, 9, 1),
            total_sessoes=10,
            status="ATIVO",
        )
        db.session.add(ciclo)
        db.session.commit()
        return ciclo.id


def agendar(client, paciente_id, hora="09:00", **campos):
    dados = {
        "paciente_id": str(paciente_id),
        "tipo": "AVALIACAO",
        "data": "2026-10-05",
        "hora": hora,
    }
    dados.update(campos)
    return client.post("/agenda/novo", data=dados, follow_redirects=True)


def test_agendar_avaliacao_grava_no_banco(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Bruno Dias", id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    agendar(client, id_paciente)

    with app.app_context():
        item = db.session.scalar(db.select(Appointment))
        assert item is not None
        assert item.tipo == "AVALIACAO"
        assert item.status == "AGENDADO"
        assert item.numero_sessao is None
        assert item.data == date(2026, 10, 5)


def test_sessao_so_avanca_apos_a_anterior_ser_realizada(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Bruno Dias", id_fisio)
    id_ciclo = criar_ciclo(app, id_paciente, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    agendar(client, id_paciente, hora="09:00", tipo="SESSAO", ciclo_id=str(id_ciclo))

    with app.app_context():
        primeira = db.session.scalar(db.select(Appointment))
        assert primeira.numero_sessao == 1
        primeira.status = "REALIZADO"
        db.session.commit()

    agendar(client, id_paciente, hora="10:00", tipo="SESSAO", ciclo_id=str(id_ciclo))

    with app.app_context():
        numeros = [
            item.numero_sessao
            for item in db.session.scalars(
                db.select(Appointment).order_by(Appointment.hora)
            ).all()
        ]
        assert numeros == [1, 2]


def test_falta_nao_consome_sessao_do_ciclo(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Bruno Dias", id_fisio)
    id_ciclo = criar_ciclo(app, id_paciente, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    agendar(client, id_paciente, hora="09:00", tipo="SESSAO", ciclo_id=str(id_ciclo))

    with app.app_context():
        faltou = db.session.scalar(db.select(Appointment))
        faltou.status = "FALTOU"
        db.session.commit()

    agendar(client, id_paciente, hora="10:00", tipo="SESSAO", ciclo_id=str(id_ciclo))

    with app.app_context():
        reposicao = db.session.scalar(
            db.select(Appointment).order_by(Appointment.hora.desc())
        )
        assert reposicao.numero_sessao == 1


def test_sessao_sem_ciclo_e_recusada(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Bruno Dias", id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(
        "/agenda/novo",
        data={
            "paciente_id": str(id_paciente),
            "tipo": "SESSAO",
            "data": "2026-10-05",
            "hora": "09:00",
        },
    )
    assert resposta.status_code == 400


def test_terceiro_paciente_no_mesmo_horario_e_recusado(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    primeiro = criar_paciente(app, "Paciente Um", id_fisio)
    segundo = criar_paciente(app, "Paciente Dois", id_fisio)
    terceiro = criar_paciente(app, "Paciente Tres", id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    agendar(client, primeiro)
    agendar(client, segundo)

    resposta = client.post(
        "/agenda/novo",
        data={
            "paciente_id": str(terceiro),
            "tipo": "AVALIACAO",
            "data": "2026-10-05",
            "hora": "09:00",
        },
    )

    assert resposta.status_code == 400
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Appointment.id))) == 2


def test_cancelado_libera_a_vaga_do_horario(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    primeiro = criar_paciente(app, "Paciente Um", id_fisio)
    segundo = criar_paciente(app, "Paciente Dois", id_fisio)
    terceiro = criar_paciente(app, "Paciente Tres", id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    agendar(client, primeiro)
    agendar(client, segundo)

    with app.app_context():
        primeiro_id = db.session.scalar(db.select(Appointment.id))

    client.post(
        f"/agendamentos/{primeiro_id}/status",
        data={"status": "CANCELADO"},
        follow_redirects=True,
    )
    agendar(client, terceiro)

    with app.app_context():
        ativos = db.session.scalar(
            db.select(db.func.count(Appointment.id)).where(
                Appointment.status != "CANCELADO"
            )
        )
        assert ativos == 2


def test_horarios_de_profissionais_diferentes_nao_conflitam(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_admin = id_do_usuario(app, "admin@teste.com")
    do_fisio = criar_paciente(app, "Do Fisio Um", id_fisio)
    do_fisio_2 = criar_paciente(app, "Do Fisio Dois", id_fisio)
    do_admin = criar_paciente(app, "Do Admin", id_admin)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    agendar(client, do_fisio)
    agendar(client, do_fisio_2)
    agendar(client, do_admin)

    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Appointment.id))) == 3


def test_fisioterapeuta_nao_agenda_paciente_alheio(client, app):
    id_admin = id_do_usuario(app, "admin@teste.com")
    alheio = criar_paciente(app, "Do Admin", id_admin)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(
        "/agenda/novo",
        data={
            "paciente_id": str(alheio),
            "tipo": "AVALIACAO",
            "data": "2026-10-05",
            "hora": "09:00",
        },
    )
    assert resposta.status_code == 403


def test_agenda_do_fisioterapeuta_mostra_so_os_dele(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_admin = id_do_usuario(app, "admin@teste.com")
    do_fisio = criar_paciente(app, "Paciente Do Fisio", id_fisio)
    do_admin = criar_paciente(app, "Paciente Do Admin", id_admin)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    agendar(client, do_fisio)
    agendar(client, do_admin, hora="11:00")
    client.post("/logout")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/agenda?data=2026-10-05").get_data(as_text=True)

    assert "Paciente Do Fisio" in corpo
    assert "Paciente Do Admin" not in corpo


def test_cpf_invalido_e_recusado(client):
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    resposta = client.post(
        "/pacientes/novo", data={"nome": "Teste CPF", "cpf": "111.111.111-11"}
    )
    assert resposta.status_code == 400


def test_cpf_valido_e_gravado_sem_pontuacao(client, app):
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    client.post(
        "/pacientes/novo",
        data={"nome": "Teste CPF", "cpf": "529.982.247-25"},
        follow_redirects=True,
    )

    with app.app_context():
        paciente = db.session.scalar(
            db.select(Patient).where(Patient.nome == "Teste CPF")
        )
        assert paciente.cpf == "52998224725"


def test_cpf_duplicado_e_recusado(client, app):
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    client.post(
        "/pacientes/novo",
        data={"nome": "Primeiro", "cpf": "529.982.247-25"},
        follow_redirects=True,
    )
    resposta = client.post(
        "/pacientes/novo", data={"nome": "Segundo", "cpf": "52998224725"}
    )
    assert resposta.status_code == 400
