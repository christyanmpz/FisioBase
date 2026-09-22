"""Encontros do grupo, inscrição vinculada e lista de presença.

O tratamento em grupo é fechado: um encontro de 1 hora por semana, que
vale por 2 sessões individuais, seis semanas fechando 12 sessões. Não há
reposição de encontro perdido.
"""

from datetime import date, time, timedelta

import app as modulo_app
from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from models import (
    Appointment,
    Group,
    GroupPatient,
    Holiday,
    Patient,
    TreatmentCycle,
    User,
    db,
)

# 06/10/2026 é uma terça-feira.
TERCA = 1
PRIMEIRO = date(2026, 10, 6)
HOJE = date(2026, 9, 28)


def fixar_hoje(monkeypatch, dia=HOJE):
    monkeypatch.setattr(modulo_app, "hoje", lambda: dia)


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def criar_grupo(app, id_fisio, **campos):
    dados = {
        "nome": "Grupo Ombro manhã",
        "regiao": "OMBRO",
        "fisioterapeuta_id": id_fisio,
        "dia_semana": TERCA,
        "hora": time(8, 0),
        "capacidade_max": 14,
        "total_semanas": 6,
        "ativo": True,
    }
    dados.update(campos)
    with app.app_context():
        grupo = Group(**dados)
        db.session.add(grupo)
        db.session.commit()
        return grupo.id


def criar_paciente(app, id_fisio, nome="Ana Prado"):
    with app.app_context():
        paciente = Patient(nome=nome, fisioterapeuta_id=id_fisio, ativo=True)
        db.session.add(paciente)
        db.session.commit()
        return paciente.id


def gerar(client, id_grupo, inicio=PRIMEIRO, semanas=6):
    return client.post(
        f"/grupos/{id_grupo}/sessoes",
        data={"inicio": inicio.isoformat(), "semanas": str(semanas)},
        follow_redirects=True,
    )


def inscrever(client, id_grupo, id_paciente):
    return client.post(
        f"/grupos/{id_grupo}/pacientes",
        data={"paciente_id": str(id_paciente)},
        follow_redirects=True,
    )


def encontros(app, id_grupo):
    with app.app_context():
        return (
            Appointment.query.filter_by(grupo_id=id_grupo, tipo="GRUPO")
            .order_by(Appointment.data)
            .all()
        )


def presencas(app, id_grupo, id_paciente):
    with app.app_context():
        return (
            Appointment.query.filter_by(grupo_id=id_grupo, paciente_id=id_paciente)
            .order_by(Appointment.data)
            .all()
        )


# ----------------------------------------------------------------------
# Gerar o calendário do grupo
# ----------------------------------------------------------------------


def test_gera_um_encontro_por_semana(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_grupo, semanas=6)

    lista = encontros(app, id_grupo)
    assert len(lista) == 6
    assert [e.data for e in lista] == [
        PRIMEIRO + timedelta(days=7 * n) for n in range(6)
    ]
    assert all(e.data.weekday() == TERCA for e in lista)
    assert all(e.hora == time(8, 0) for e in lista)
    assert all(e.duracao_min == 60 for e in lista)
    assert all(e.paciente_id is None for e in lista)


def test_encontro_pula_feriado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)

    segundo = PRIMEIRO + timedelta(days=7)
    with app.app_context():
        db.session.add(Holiday(data=segundo, nome="Feriado", tipo="MUNICIPAL"))
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_grupo, semanas=3)

    datas = [e.data for e in encontros(app, id_grupo)]
    assert segundo not in datas
    assert len(datas) == 3


def test_nao_gera_duas_vezes(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_grupo, semanas=6)
    resposta = gerar(client, id_grupo, semanas=6)

    assert "já tem encontros marcados" in resposta.get_data(as_text=True)
    assert len(encontros(app, id_grupo)) == 6


def test_grupo_desativado_nao_gera(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio, ativo=False)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = gerar(client, id_grupo)

    assert "desativado" in resposta.get_data(as_text=True)
    assert encontros(app, id_grupo) == []


def test_data_no_passado_e_recusada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = gerar(client, id_grupo, inicio=date(2026, 9, 1))

    assert "não pode estar no passado" in resposta.get_data(as_text=True)
    assert encontros(app, id_grupo) == []


# ----------------------------------------------------------------------
# A inscrição vira ciclo e cartão
# ----------------------------------------------------------------------


def test_inscricao_cria_o_ciclo_do_grupo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_grupo, semanas=6)
    inscrever(client, id_grupo, id_paciente)

    with app.app_context():
        ciclo = db.session.scalar(
            db.select(TreatmentCycle).where(TreatmentCycle.paciente_id == id_paciente)
        )
        assert ciclo is not None
        assert ciclo.modalidade == "GRUPO"
        assert ciclo.regiao == "OMBRO"
        # 6 encontros de 1 hora = 12 sessões individuais.
        assert ciclo.total_sessoes == 12


def test_inscricao_cria_uma_presenca_por_encontro(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_grupo, semanas=6)
    inscrever(client, id_grupo, id_paciente)

    lista = presencas(app, id_grupo, id_paciente)
    assert len(lista) == 6
    assert [p.numero_sessao for p in lista] == [2, 4, 6, 8, 10, 12]
    assert all(p.duracao_min == 60 for p in lista)


def test_quem_entra_depois_pega_so_o_que_falta(client, app, monkeypatch):
    """Entrou na terceira semana: o cartão dele não promete datas passadas."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_grupo, semanas=6)

    # Duas semanas depois do primeiro encontro.
    fixar_hoje(monkeypatch, PRIMEIRO + timedelta(days=14))
    inscrever(client, id_grupo, id_paciente)

    lista = presencas(app, id_grupo, id_paciente)
    assert len(lista) == 4
    with app.app_context():
        ciclo = db.session.scalar(
            db.select(TreatmentCycle).where(TreatmentCycle.paciente_id == id_paciente)
        )
        assert ciclo.total_sessoes == 8


def test_quem_ja_estava_inscrito_entra_ao_gerar(client, app, monkeypatch):
    """Inscreveu antes do calendário existir; ao gerar, recebe as datas."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    inscrever(client, id_grupo, id_paciente)
    assert presencas(app, id_grupo, id_paciente) == []

    gerar(client, id_grupo, semanas=6)

    assert len(presencas(app, id_grupo, id_paciente)) == 6
    with app.app_context():
        participacao = db.session.scalar(db.select(GroupPatient))
        assert participacao.ciclo_id is not None


def test_presenca_no_grupo_nao_ocupa_a_agenda_individual(client, app, monkeypatch):
    """14 inscritos não podem bloquear o horário para atendimento normal.

    O limite é de 2 pacientes por horário. Se cada presença no grupo
    contasse, o horário do grupo ficaria cheio já no terceiro inscrito e
    nenhum atendimento individual caberia mais ali.
    """
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_grupo, semanas=6)
    for numero in range(3):
        inscrever(client, id_grupo, criar_paciente(app, id_fisio, f"Inscrito {numero}"))

    # Um paciente individual no mesmo dia e horário do grupo.
    id_avulso = criar_paciente(app, id_fisio, "Atendimento Individual")
    with app.app_context():
        ciclo = TreatmentCycle(
            paciente_id=id_avulso,
            fisioterapeuta_id=id_fisio,
            regiao="JOELHO",
            modalidade="INDIVIDUAL",
            data_avaliacao=HOJE,
            total_sessoes=10,
            status="ATIVO",
        )
        db.session.add(ciclo)
        db.session.commit()
        id_ciclo = ciclo.id

    resposta = client.post(
        "/agenda/novo",
        data={
            "tipo": "SESSAO",
            "paciente_id": str(id_avulso),
            "ciclo_id": str(id_ciclo),
            "data": PRIMEIRO.isoformat(),
            "hora": "08:00",
        },
        follow_redirects=True,
    )

    assert "já tem 2 pacientes" not in resposta.get_data(as_text=True)
    with app.app_context():
        assert (
            Appointment.query.filter_by(
                paciente_id=id_avulso, data=PRIMEIRO, hora=time(8, 0)
            ).count()
            == 1
        )


def test_presenca_no_grupo_nao_aparece_na_agenda_do_dia(client, app, monkeypatch):
    """A grade mostra o grupo uma vez, não uma linha por inscrito."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_grupo, semanas=6)
    inscrever(client, id_grupo, criar_paciente(app, id_fisio, "Inscrito No Grupo"))

    for rota in ["/agenda", "/agenda/dia", "/agenda/semana"]:
        pagina = client.get(f"{rota}?data={PRIMEIRO.isoformat()}").get_data(
            as_text=True
        )
        assert "Inscrito No Grupo" not in pagina, rota
        assert "Grupo Ombro manhã" in pagina, rota


# ----------------------------------------------------------------------
# Lista de presença
# ----------------------------------------------------------------------


def test_lista_de_presenca_mostra_inscritos_e_datas(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio, "Jussara Neves")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_grupo, semanas=3)
    inscrever(client, id_grupo, id_paciente)

    pagina = client.get(f"/grupos/{id_grupo}/presenca").get_data(as_text=True)

    assert "Jussara Neves" in pagina
    assert PRIMEIRO.strftime("%d/%m") in pagina
    assert (PRIMEIRO + timedelta(days=14)).strftime("%d/%m") in pagina


def test_marca_presenca_no_dia_do_encontro(client, app, monkeypatch):
    fixar_hoje(monkeypatch, PRIMEIRO)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_grupo, semanas=3)
    inscrever(client, id_grupo, id_paciente)

    primeira = presencas(app, id_grupo, id_paciente)[0]
    client.post(
        f"/grupos/{id_grupo}/presenca/{primeira.id}",
        data={"status": "REALIZADO"},
        follow_redirects=True,
    )

    assert presencas(app, id_grupo, id_paciente)[0].status == "REALIZADO"


def test_comparecimento_antes_do_dia_e_recusado(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_grupo, semanas=3)
    inscrever(client, id_grupo, id_paciente)

    primeira = presencas(app, id_grupo, id_paciente)[0]
    resposta = client.post(
        f"/grupos/{id_grupo}/presenca/{primeira.id}",
        data={"status": "REALIZADO"},
        follow_redirects=True,
    )

    assert "a partir do dia do encontro" in resposta.get_data(as_text=True)
    assert presencas(app, id_grupo, id_paciente)[0].status == "AGENDADO"


def test_falta_justificada_antes_do_dia_e_aceita(client, app, monkeypatch):
    """O paciente avisa com antecedência; a regra é a mesma do individual."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_grupo, semanas=3)
    inscrever(client, id_grupo, id_paciente)

    primeira = presencas(app, id_grupo, id_paciente)[0]
    client.post(
        f"/grupos/{id_grupo}/presenca/{primeira.id}",
        data={"status": "FALTA_JUSTIFICADA", "justificativa": "Consulta médica."},
        follow_redirects=True,
    )

    salva = presencas(app, id_grupo, id_paciente)[0]
    assert salva.status == "FALTA_JUSTIFICADA"
    assert salva.observacoes == "Consulta médica."


def test_falta_justificada_sem_motivo_e_recusada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_grupo, semanas=3)
    inscrever(client, id_grupo, id_paciente)

    primeira = presencas(app, id_grupo, id_paciente)[0]
    resposta = client.post(
        f"/grupos/{id_grupo}/presenca/{primeira.id}",
        data={"status": "FALTA_JUSTIFICADA"},
        follow_redirects=True,
    )

    assert "Informe o motivo" in resposta.get_data(as_text=True)
    assert presencas(app, id_grupo, id_paciente)[0].status == "AGENDADO"


def test_grupo_nao_gera_reposicao(client, app, monkeypatch):
    """Regra da clínica: encontro perdido no grupo não é reposto."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    gerar(client, id_grupo, semanas=3)
    inscrever(client, id_grupo, id_paciente)

    primeira = presencas(app, id_grupo, id_paciente)[0]
    client.post(
        f"/grupos/{id_grupo}/presenca/{primeira.id}",
        data={"status": "FALTA_JUSTIFICADA", "justificativa": "Viagem."},
        follow_redirects=True,
    )

    assert len(presencas(app, id_grupo, id_paciente)) == 3


def test_outro_fisioterapeuta_nao_abre_a_lista(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_admin = id_do_usuario(app, "admin@teste.com")
    id_grupo = criar_grupo(app, id_admin)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert client.get(f"/grupos/{id_grupo}/presenca").status_code == 403
    assert client.get(f"/grupos/{id_grupo}/sessoes").status_code == 403


def test_admin_conduz_qualquer_grupo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    gerar(client, id_grupo, semanas=2)

    assert len(encontros(app, id_grupo)) == 2
