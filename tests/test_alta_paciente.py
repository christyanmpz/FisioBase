"""Alta do paciente, reativação e a regra que precede o tratamento.

Sair da clínica é alta, não exclusão: o cadastro e o histórico continuam
inteiros e o paciente pode voltar sem recadastro. E o ciclo de tratamento
só é aberto depois que ele compareceu à avaliação — ou entrou num grupo,
onde a avaliação acontece no primeiro encontro.
"""

from datetime import date, time, timedelta

import app as modulo_app
from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from models import (
    Appointment,
    Group,
    GroupPatient,
    Patient,
    TreatmentCycle,
    User,
    db,
)

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


def marcar_avaliacao(app, id_paciente, id_fisio, status="REALIZADO", dia=HOJE):
    with app.app_context():
        avaliacao = Appointment(
            tipo="AVALIACAO",
            paciente_id=id_paciente,
            fisioterapeuta_id=id_fisio,
            data=dia,
            hora=time(13, 30),
            duracao_min=30,
            status=status,
        )
        db.session.add(avaliacao)
        db.session.commit()
        return avaliacao.id


def abrir_ciclo(client, id_paciente):
    return client.post(
        f"/pacientes/{id_paciente}/ciclos/novo",
        data={
            "data_avaliacao": "2026-09-01",
            "regiao": "JOELHO",
            "modalidade": "INDIVIDUAL",
            "total_sessoes": "10",
        },
        follow_redirects=True,
    )


def ciclos(app, id_paciente):
    with app.app_context():
        return TreatmentCycle.query.filter_by(paciente_id=id_paciente).all()


# ----------------------------------------------------------------------
# O tratamento vem depois da avaliação
# ----------------------------------------------------------------------


def test_sem_avaliacao_nao_abre_ciclo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = abrir_ciclo(client, id_paciente)

    assert "ainda não compareceu a uma avaliação" in resposta.get_data(as_text=True)
    assert ciclos(app, id_paciente) == []


def test_avaliacao_so_marcada_nao_basta(client, app, monkeypatch):
    """Agendada não é comparecida: a regra é o comparecimento."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)
    marcar_avaliacao(app, id_paciente, id_fisio, status="AGENDADO")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    abrir_ciclo(client, id_paciente)

    assert ciclos(app, id_paciente) == []


def test_depois_de_comparecer_abre_o_ciclo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)
    marcar_avaliacao(app, id_paciente, id_fisio, status="REALIZADO")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    abrir_ciclo(client, id_paciente)

    assert len(ciclos(app, id_paciente)) == 1


def test_falta_justificada_na_avaliacao_tambem_libera(client, app, monkeypatch):
    """A clínica conta falta justificada como atendimento realizado."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)
    marcar_avaliacao(app, id_paciente, id_fisio, status="FALTA_JUSTIFICADA")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    abrir_ciclo(client, id_paciente)

    assert len(ciclos(app, id_paciente)) == 1


def test_inscrito_em_grupo_abre_ciclo_sem_avaliacao(client, app, monkeypatch):
    """No grupo a avaliação acontece no primeiro encontro."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)

    with app.app_context():
        grupo = Group(
            nome="Grupo Joelho",
            regiao="JOELHO",
            fisioterapeuta_id=id_fisio,
            dia_semana=1,
            hora=time(8, 0),
            capacidade_max=14,
            ativo=True,
        )
        db.session.add(grupo)
        db.session.flush()
        db.session.add(
            GroupPatient(grupo_id=grupo.id, paciente_id=id_paciente, data_entrada=HOJE)
        )
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    abrir_ciclo(client, id_paciente)

    assert len(ciclos(app, id_paciente)) == 1


# ----------------------------------------------------------------------
# Alta do paciente
# ----------------------------------------------------------------------


def test_alta_guarda_data_e_motivo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    client.post(
        f"/pacientes/{id_paciente}/alta",
        data={"motivo": "Alta por melhora; orientado a manter exercícios."},
        follow_redirects=True,
    )

    with app.app_context():
        paciente = db.session.get(Patient, id_paciente)
        assert paciente.ativo is False
        assert paciente.data_alta == HOJE
        assert "melhora" in paciente.motivo_alta


def test_alta_sem_motivo_e_recusada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(
        f"/pacientes/{id_paciente}/alta", data={}, follow_redirects=True
    )

    assert "Informe o motivo da alta" in resposta.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Patient, id_paciente).ativo is True


def test_alta_encerra_ciclo_ativo_e_cancela_o_futuro(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)

    with app.app_context():
        ciclo = TreatmentCycle(
            paciente_id=id_paciente,
            fisioterapeuta_id=id_fisio,
            regiao="OMBRO",
            modalidade="INDIVIDUAL",
            data_avaliacao=HOJE,
            total_sessoes=10,
            status="ATIVO",
        )
        db.session.add(ciclo)
        db.session.flush()
        db.session.add(
            Appointment(
                tipo="SESSAO",
                paciente_id=id_paciente,
                ciclo_id=ciclo.id,
                fisioterapeuta_id=id_fisio,
                data=HOJE + timedelta(days=7),
                hora=time(9, 0),
                duracao_min=30,
                status="AGENDADO",
            )
        )
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    client.post(
        f"/pacientes/{id_paciente}/alta",
        data={"motivo": "Mudou de cidade."},
        follow_redirects=True,
    )

    with app.app_context():
        assert db.session.scalar(db.select(TreatmentCycle)).status == "ALTA"
        assert db.session.scalar(db.select(Appointment)).status == "CANCELADO"


def test_paciente_de_alta_continua_pesquisavel(client, app, monkeypatch):
    """A clínica reclamou que o paciente sumia da lista. Ele não some."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio, "Josue Silva")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    client.post(
        f"/pacientes/{id_paciente}/alta",
        data={"motivo": "Alta por melhora."},
        follow_redirects=True,
    )

    # No filtro padrão ele sai; nos outros dois continua lá.
    assert "Josue Silva" not in client.get("/pacientes").get_data(as_text=True)
    assert "Josue Silva" in client.get("/pacientes?situacao=alta").get_data(
        as_text=True
    )
    assert "Josue Silva" in client.get("/pacientes?situacao=todos").get_data(
        as_text=True
    )


def test_ficha_mostra_a_ultima_alta(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    client.post(
        f"/pacientes/{id_paciente}/alta",
        data={"motivo": "Concluiu o tratamento do ombro."},
        follow_redirects=True,
    )

    pagina = client.get(f"/pacientes/{id_paciente}").get_data(as_text=True)

    assert "Última alta" in pagina
    assert "Concluiu o tratamento do ombro." in pagina
    assert "Reativar paciente" in pagina


# ----------------------------------------------------------------------
# Reativação
# ----------------------------------------------------------------------


def test_reativar_traz_o_paciente_de_volta(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    client.post(
        f"/pacientes/{id_paciente}/alta",
        data={"motivo": "Alta por melhora."},
        follow_redirects=True,
    )
    client.post(f"/pacientes/{id_paciente}/reativar", follow_redirects=True)

    with app.app_context():
        paciente = db.session.get(Patient, id_paciente)
        assert paciente.ativo is True
        # A alta anterior continua registrada: é o histórico da última saída.
        assert paciente.data_alta == HOJE
        assert paciente.motivo_alta is not None


def test_reativar_quem_ja_esta_ativo_avisa(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(f"/pacientes/{id_paciente}/reativar", follow_redirects=True)

    assert "já está em acompanhamento" in resposta.get_data(as_text=True)


def test_fisioterapeuta_nao_reativa_paciente_de_outro(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_admin = id_do_usuario(app, "admin@teste.com")
    id_alheio = criar_paciente(app, id_admin, "Paciente Do Admin")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert client.post(f"/pacientes/{id_alheio}/reativar").status_code == 403


# ----------------------------------------------------------------------
# Alta direto na avaliação
# ----------------------------------------------------------------------


def test_alta_na_avaliacao_nao_abre_ciclo(client, app, monkeypatch):
    """Condição boa: o paciente sai orientado, sem tratamento."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)
    id_avaliacao = marcar_avaliacao(app, id_paciente, id_fisio, status="AGENDADO")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    client.post(
        f"/triagem/{id_avaliacao}/alta",
        data={"orientacao": "Exercícios de fortalecimento em domicílio."},
        follow_redirects=True,
    )

    with app.app_context():
        paciente = db.session.get(Patient, id_paciente)
        avaliacao = db.session.get(Appointment, id_avaliacao)
        assert paciente.ativo is False
        assert "domicílio" in paciente.motivo_alta
        assert avaliacao.status == "REALIZADO"
        assert "Alta na avaliação" in avaliacao.observacoes
    assert ciclos(app, id_paciente) == []


def test_alta_na_avaliacao_antes_do_dia_e_recusada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)
    id_avaliacao = marcar_avaliacao(
        app, id_paciente, id_fisio, status="AGENDADO", dia=HOJE + timedelta(days=7)
    )

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(
        f"/triagem/{id_avaliacao}/alta",
        data={"orientacao": "Adiantando."},
        follow_redirects=True,
    )

    assert "a partir do dia da avaliação" in resposta.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Patient, id_paciente).ativo is True


def test_alta_na_avaliacao_sem_orientacao_e_recusada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)
    id_avaliacao = marcar_avaliacao(app, id_paciente, id_fisio, status="AGENDADO")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(
        f"/triagem/{id_avaliacao}/alta", data={}, follow_redirects=True
    )

    assert "Descreva a orientação" in resposta.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Patient, id_paciente).ativo is True


def test_alta_na_avaliacao_exige_que_seja_avaliacao(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)

    with app.app_context():
        sessao = Appointment(
            tipo="SESSAO",
            paciente_id=id_paciente,
            fisioterapeuta_id=id_fisio,
            data=HOJE,
            hora=time(9, 0),
            duracao_min=30,
            status="AGENDADO",
        )
        db.session.add(sessao)
        db.session.commit()
        id_sessao = sessao.id

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(
        f"/triagem/{id_sessao}/alta", data={"orientacao": "Qualquer coisa."}
    )

    assert resposta.status_code == 404


def test_admin_da_alta_em_qualquer_paciente(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    client.post(
        f"/pacientes/{id_paciente}/alta",
        data={"motivo": "Transferido para outra unidade."},
        follow_redirects=True,
    )

    with app.app_context():
        assert db.session.get(Patient, id_paciente).ativo is False
