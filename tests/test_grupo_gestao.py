"""Evolução do grupo, motivo da saída e a tela de listagem.

No grupo a evolução é do encontro inteiro: os exercícios são os mesmos
para todos os inscritos, e o que muda por pessoa é só a presença.
"""

from datetime import date, time, timedelta

import app as modulo_app
from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from models import (
    Appointment,
    Group,
    GroupEvolution,
    GroupPatient,
    Patient,
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


def montar(client, app, id_fisio, semanas=3, nome="Ana Prado"):
    """Grupo com encontros gerados e um paciente inscrito."""
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio, nome)
    client.post(
        f"/grupos/{id_grupo}/sessoes",
        data={"inicio": PRIMEIRO.isoformat(), "semanas": str(semanas)},
        follow_redirects=True,
    )
    client.post(
        f"/grupos/{id_grupo}/pacientes",
        data={"paciente_id": str(id_paciente)},
        follow_redirects=True,
    )
    return id_grupo, id_paciente


def encontros(app, id_grupo):
    with app.app_context():
        return (
            Appointment.query.filter_by(grupo_id=id_grupo, tipo="GRUPO")
            .order_by(Appointment.data)
            .all()
        )


# ----------------------------------------------------------------------
# Evolução do encontro
# ----------------------------------------------------------------------


def test_registra_a_evolucao_do_encontro(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    id_grupo, _ = montar(client, app, id_fisio)

    fixar_hoje(monkeypatch, PRIMEIRO)
    primeiro = encontros(app, id_grupo)[0]
    client.post(
        f"/grupos/{id_grupo}/encontros/{primeiro.id}/evolucao",
        data={
            "descricao": "Mobilização escapular e fortalecimento com elástico.",
            "observacoes": "Grupo respondeu bem; aumentar carga na semana que vem.",
        },
        follow_redirects=True,
    )

    with app.app_context():
        evolucao = db.session.scalar(db.select(GroupEvolution))
        assert evolucao is not None
        assert evolucao.data == PRIMEIRO
        assert "Mobilização escapular" in evolucao.descricao
        assert "aumentar carga" in evolucao.observacoes


def test_evolucao_antes_do_encontro_e_recusada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    id_grupo, _ = montar(client, app, id_fisio)

    primeiro = encontros(app, id_grupo)[0]
    resposta = client.post(
        f"/grupos/{id_grupo}/encontros/{primeiro.id}/evolucao",
        data={"descricao": "Adiantando o relato."},
        follow_redirects=True,
    )

    assert "a partir do dia do encontro" in resposta.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(GroupEvolution)) is None


def test_evolucao_sem_descricao_e_recusada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    id_grupo, _ = montar(client, app, id_fisio)

    fixar_hoje(monkeypatch, PRIMEIRO)
    primeiro = encontros(app, id_grupo)[0]
    resposta = client.post(
        f"/grupos/{id_grupo}/encontros/{primeiro.id}/evolucao",
        data={"descricao": "   ", "observacoes": "algo"},
        follow_redirects=True,
    )

    assert "Descreva o que foi feito" in resposta.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(GroupEvolution)) is None


def test_salvar_de_novo_corrige_em_vez_de_duplicar(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    id_grupo, _ = montar(client, app, id_fisio)

    fixar_hoje(monkeypatch, PRIMEIRO)
    primeiro = encontros(app, id_grupo)[0]
    rota = f"/grupos/{id_grupo}/encontros/{primeiro.id}/evolucao"
    client.post(rota, data={"descricao": "Primeira versao."}, follow_redirects=True)
    client.post(rota, data={"descricao": "Versao corrigida."}, follow_redirects=True)

    with app.app_context():
        todas = GroupEvolution.query.all()
        assert len(todas) == 1
        assert todas[0].descricao == "Versao corrigida."


def test_evolucao_aparece_na_lista_de_encontros(client, app, monkeypatch):
    fixar_hoje(monkeypatch, PRIMEIRO)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    id_grupo, _ = montar(client, app, id_fisio)

    primeiro = encontros(app, id_grupo)[0]
    client.post(
        f"/grupos/{id_grupo}/encontros/{primeiro.id}/evolucao",
        data={"descricao": "Alongamento e fortalecimento."},
        follow_redirects=True,
    )

    pagina = client.get(f"/grupos/{id_grupo}/sessoes").get_data(as_text=True)
    assert "Editar" in pagina


def test_outro_fisioterapeuta_nao_registra_evolucao(client, app, monkeypatch):
    fixar_hoje(monkeypatch, PRIMEIRO)
    id_admin = id_do_usuario(app, "admin@teste.com")
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    id_grupo, _ = montar(client, app, id_admin)
    primeiro = encontros(app, id_grupo)[0]

    # Sem sair antes, o login novo não troca de usuário.
    client.post("/logout")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.get(f"/grupos/{id_grupo}/encontros/{primeiro.id}/evolucao")

    assert resposta.status_code == 403


# ----------------------------------------------------------------------
# Motivo da saída
# ----------------------------------------------------------------------


def test_saida_guarda_o_motivo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    id_grupo, _ = montar(client, app, id_fisio)

    with app.app_context():
        id_participacao = db.session.scalar(db.select(GroupPatient)).id

    client.post(
        f"/grupos/{id_grupo}/pacientes/{id_participacao}/saida",
        data={"motivo": "Pedido do paciente, mudou de horário no trabalho."},
        follow_redirects=True,
    )

    with app.app_context():
        participacao = db.session.get(GroupPatient, id_participacao)
        assert participacao.data_saida == HOJE
        assert "mudou de horário" in participacao.motivo_saida


def test_saida_sem_motivo_continua_funcionando(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    id_grupo, _ = montar(client, app, id_fisio)

    with app.app_context():
        id_participacao = db.session.scalar(db.select(GroupPatient)).id

    client.post(
        f"/grupos/{id_grupo}/pacientes/{id_participacao}/saida",
        data={},
        follow_redirects=True,
    )

    with app.app_context():
        participacao = db.session.get(GroupPatient, id_participacao)
        assert participacao.data_saida == HOJE
        assert participacao.motivo_saida is None


def test_saida_cancela_as_datas_que_faltam(client, app, monkeypatch):
    """Quem saiu não pode continuar ocupando a lista de presença futura."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    id_grupo, id_paciente = montar(client, app, id_fisio, semanas=3)

    with app.app_context():
        id_participacao = db.session.scalar(db.select(GroupPatient)).id

    client.post(
        f"/grupos/{id_grupo}/pacientes/{id_participacao}/saida",
        data={"motivo": "Alta."},
        follow_redirects=True,
    )

    with app.app_context():
        pendentes = Appointment.query.filter(
            Appointment.grupo_id == id_grupo,
            Appointment.paciente_id == id_paciente,
            Appointment.status != "CANCELADO",
        ).count()
        assert pendentes == 0


# ----------------------------------------------------------------------
# Tela de listagem
# ----------------------------------------------------------------------


def test_grupo_desativado_nao_abre_a_edicao(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio, ativo=False)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.get(f"/grupos/{id_grupo}/editar", follow_redirects=True)

    assert "não pode ser editado" in resposta.get_data(as_text=True)


def test_filtro_por_tipo_de_grupo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_grupo(app, id_fisio, nome="Grupo do Ombro", regiao="OMBRO")
    criar_grupo(app, id_fisio, nome="Grupo da Coluna", regiao="COLUNA")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get("/grupos?regiao=COLUNA").get_data(as_text=True)

    assert "Grupo da Coluna" in pagina
    assert "Grupo do Ombro" not in pagina


def test_mais_recentes_no_topo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_grupo(app, id_fisio, nome="Grupo Antigo")
    criar_grupo(app, id_fisio, nome="Grupo Novo")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get("/grupos").get_data(as_text=True)

    assert pagina.index("Grupo Novo") < pagina.index("Grupo Antigo")


def test_consulta_se_o_paciente_esta_em_algum_grupo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    montar(client, app, id_fisio, nome="Jussara Neves")
    criar_grupo(app, id_fisio, nome="Grupo Sem Ela", regiao="COLUNA")

    pagina = client.get("/grupos?paciente=Jussara").get_data(as_text=True)

    assert "Grupo Ombro manhã" in pagina
    assert "Grupo Sem Ela" not in pagina
    assert "inscrito desde" in pagina


def test_consulta_acha_quem_ja_saiu(client, app, monkeypatch):
    """O PDF pede saber também quem já participou de um grupo que terminou."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    id_grupo, _ = montar(client, app, id_fisio, nome="Jussara Neves")

    with app.app_context():
        id_participacao = db.session.scalar(db.select(GroupPatient)).id
    client.post(
        f"/grupos/{id_grupo}/pacientes/{id_participacao}/saida",
        data={"motivo": "Alta."},
        follow_redirects=True,
    )

    pagina = client.get("/grupos?paciente=Jussara").get_data(as_text=True)

    assert "Grupo Ombro manhã" in pagina
    assert "saiu em" in pagina


def test_filtro_sem_resultado_avisa(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_grupo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = client.get("/grupos?paciente=NinguemComEsseNome").get_data(as_text=True)

    assert "Nenhum grupo encontrado com esse filtro" in pagina


# ----------------------------------------------------------------------
# Resumo impresso
# ----------------------------------------------------------------------


def test_resumo_traz_presenca_e_evolucao(client, app, monkeypatch):
    fixar_hoje(monkeypatch, PRIMEIRO)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    id_grupo, id_paciente = montar(client, app, id_fisio, nome="Jussara Neves")

    primeiro = encontros(app, id_grupo)[0]
    client.post(
        f"/grupos/{id_grupo}/encontros/{primeiro.id}/evolucao",
        data={"descricao": "Mobilizacao e fortalecimento."},
        follow_redirects=True,
    )

    with app.app_context():
        presenca = Appointment.query.filter_by(
            grupo_id=id_grupo, paciente_id=id_paciente, data=PRIMEIRO
        ).first()
        id_presenca = presenca.id
    client.post(
        f"/grupos/{id_grupo}/presenca/{id_presenca}",
        data={"status": "REALIZADO"},
        follow_redirects=True,
    )

    pagina = client.get(f"/grupos/{id_grupo}/resumo").get_data(as_text=True)

    assert "Jussara Neves" in pagina
    assert "Mobilizacao e fortalecimento." in pagina
    # 1 comparecimento = 2 sessões individuais.
    assert ">2<" in pagina


def test_resumo_aponta_encontro_sem_evolucao(client, app, monkeypatch):
    fixar_hoje(monkeypatch, PRIMEIRO)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    id_grupo, _ = montar(client, app, id_fisio)

    pagina = client.get(f"/grupos/{id_grupo}/resumo").get_data(as_text=True)

    assert "Evolução não registrada" in pagina


def test_resumo_mostra_o_motivo_da_saida(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    id_grupo, _ = montar(client, app, id_fisio)

    with app.app_context():
        id_participacao = db.session.scalar(db.select(GroupPatient)).id
    client.post(
        f"/grupos/{id_grupo}/pacientes/{id_participacao}/saida",
        data={"motivo": "Conseguiu emprego no horario do grupo."},
        follow_redirects=True,
    )

    pagina = client.get(f"/grupos/{id_grupo}/resumo").get_data(as_text=True)

    assert "Conseguiu emprego no horario do grupo." in pagina


def test_outro_fisioterapeuta_nao_abre_o_resumo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_admin = id_do_usuario(app, "admin@teste.com")
    id_grupo = criar_grupo(app, id_admin)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert client.get(f"/grupos/{id_grupo}/resumo").status_code == 403
