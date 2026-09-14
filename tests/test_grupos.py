"""CRUD de grupos terapêuticos.

Criar, listar, editar e desativar. A composição do grupo (adicionar e
remover pacientes) fica em etapa separada.
"""

from datetime import time

from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from models import Group, User, db

SEGUNDA = 0
TERCA = 1
SABADO = 5


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def criar_grupo(app, fisioterapeuta_id, **campos):
    dados = {
        "nome": "Grupo Ombro manhã",
        "regiao": "OMBRO",
        "fisioterapeuta_id": fisioterapeuta_id,
        "dia_semana": SEGUNDA,
        "hora": time(8, 0),
        "capacidade_max": 14,
        "ativo": True,
    }
    dados.update(campos)
    with app.app_context():
        grupo = Group(**dados)
        db.session.add(grupo)
        db.session.commit()
        return grupo.id


def enviar(client, **campos):
    dados = {
        "nome": "Grupo Joelho tarde",
        "regiao": "JOELHO",
        "dia_semana": str(TERCA),
        "hora": "14:00",
        "capacidade_max": "14",
    }
    dados.update(campos)
    return client.post("/grupos/novo", data=dados)


def contar(app):
    with app.app_context():
        return db.session.scalar(db.select(db.func.count(Group.id)))


def buscar(app, grupo_id):
    with app.app_context():
        return db.session.get(Group, grupo_id)


# ----------------------------------------------------------------------
# Criar
# ----------------------------------------------------------------------


def test_fisioterapeuta_cria_grupo_para_si(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert enviar(client).status_code == 302

    grupo = buscar(app, 1)
    assert grupo.nome == "Grupo Joelho tarde"
    assert grupo.regiao == "JOELHO"
    assert grupo.fisioterapeuta_id == id_fisio
    assert grupo.dia_semana == TERCA
    assert grupo.hora == time(14, 0)
    assert grupo.capacidade_max == 14
    assert grupo.ativo is True


def test_capacidade_em_branco_usa_o_padrao_da_clinica(client, app):
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    enviar(client, capacidade_max="")

    assert buscar(app, 1).capacidade_max == 14


def test_admin_escolhe_quem_conduz(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    enviar(client, fisioterapeuta_id=str(id_fisio))

    assert buscar(app, 1).fisioterapeuta_id == id_fisio


def test_fisioterapeuta_nao_cria_grupo_para_outro(client, app):
    id_admin = id_do_usuario(app, "admin@teste.com")
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    enviar(client, fisioterapeuta_id=str(id_admin))

    assert buscar(app, 1).fisioterapeuta_id == id_fisio


# ----------------------------------------------------------------------
# Validações do formulário
# ----------------------------------------------------------------------


def test_nome_em_branco_e_recusado(client, app):
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert enviar(client, nome="   ").status_code == 400
    assert contar(app) == 0


def test_regiao_invalida_e_recusada(client, app):
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert enviar(client, regiao="TORNOZELO").status_code == 400
    assert contar(app) == 0


def test_sabado_e_recusado(client, app):
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert enviar(client, dia_semana=str(SABADO)).status_code == 400
    assert contar(app) == 0


def test_horario_antes_do_almoco_e_recusado(client, app):
    """11:30 + 1 hora cairia no almoço, que está fora da grade."""
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert enviar(client, hora="11:30").status_code == 400
    assert contar(app) == 0


def test_ultimo_horario_do_dia_e_recusado(client, app):
    """15:30 não tem o segundo horário: o expediente encerra às 16h."""
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert enviar(client, hora="15:30").status_code == 400
    assert contar(app) == 0


def test_horario_fora_da_grade_e_recusado(client, app):
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert enviar(client, hora="16:30").status_code == 400
    assert contar(app) == 0


def test_ultimo_horario_valido_para_grupo_e_aceito(client, app):
    """15:00 vai até 16h, encerrando junto com o expediente."""
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert enviar(client, hora="15:00").status_code == 302
    assert buscar(app, 1).hora == time(15, 0)


def test_capacidade_acima_do_limite_e_recusada(client, app):
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert enviar(client, capacidade_max="25").status_code == 400
    assert contar(app) == 0


# ----------------------------------------------------------------------
# Conflito de horário do condutor
# ----------------------------------------------------------------------


def test_dois_grupos_do_mesmo_condutor_no_mesmo_horario(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_grupo(app, id_fisio, dia_semana=TERCA, hora=time(14, 0))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    assert enviar(client, hora="14:00").status_code == 400
    assert contar(app) == 1


def test_grupo_que_comeca_no_meio_de_outro_e_recusado(client, app):
    """Grupo das 14h ocupa 14:00 e 14:30; outro às 14:30 se sobrepõe."""
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_grupo(app, id_fisio, dia_semana=TERCA, hora=time(14, 0))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    assert enviar(client, hora="14:30").status_code == 400
    assert contar(app) == 1


def test_grupo_logo_apos_o_anterior_e_aceito(client, app):
    """Grupo das 14h termina às 15h, então 15:00 está livre."""
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_grupo(app, id_fisio, dia_semana=TERCA, hora=time(14, 0))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    assert enviar(client, hora="15:00").status_code == 302
    assert contar(app) == 2


def test_mesmo_horario_em_dia_diferente_e_aceito(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_grupo(app, id_fisio, dia_semana=SEGUNDA, hora=time(14, 0))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    assert enviar(client, dia_semana=str(TERCA), hora="14:00").status_code == 302
    assert contar(app) == 2


def test_condutores_diferentes_nao_conflitam(client, app):
    id_admin = id_do_usuario(app, "admin@teste.com")
    criar_grupo(app, id_admin, dia_semana=TERCA, hora=time(14, 0))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    assert enviar(client, hora="14:00").status_code == 302
    assert contar(app) == 2


def test_grupo_desativado_nao_bloqueia_o_horario(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_grupo(app, id_fisio, dia_semana=TERCA, hora=time(14, 0), ativo=False)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    assert enviar(client, hora="14:00").status_code == 302
    assert contar(app) == 2


# ----------------------------------------------------------------------
# Listagem e escopo de acesso
# ----------------------------------------------------------------------


def test_fisioterapeuta_ve_so_os_grupos_que_conduz(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_admin = id_do_usuario(app, "admin@teste.com")
    criar_grupo(app, id_fisio, nome="Grupo do fisio")
    criar_grupo(app, id_admin, nome="Grupo do admin", hora=time(9, 0))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/grupos").get_data(as_text=True)

    assert "Grupo do fisio" in corpo
    assert "Grupo do admin" not in corpo


def test_admin_ve_todos_os_grupos(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_admin = id_do_usuario(app, "admin@teste.com")
    criar_grupo(app, id_fisio, nome="Grupo do fisio")
    criar_grupo(app, id_admin, nome="Grupo do admin", hora=time(9, 0))

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    corpo = client.get("/grupos").get_data(as_text=True)

    assert "Grupo do fisio" in corpo
    assert "Grupo do admin" in corpo


def test_grupos_exige_login(client):
    resposta = client.get("/grupos")

    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


# ----------------------------------------------------------------------
# Editar
# ----------------------------------------------------------------------


def test_condutor_edita_o_proprio_grupo(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(
        f"/grupos/{id_grupo}/editar",
        data={
            "nome": "Grupo Coluna manhã",
            "regiao": "COLUNA",
            "dia_semana": str(TERCA),
            "hora": "09:00",
            "capacidade_max": "12",
        },
    )

    assert resposta.status_code == 302
    grupo = buscar(app, id_grupo)
    assert grupo.nome == "Grupo Coluna manhã"
    assert grupo.regiao == "COLUNA"
    assert grupo.dia_semana == TERCA
    assert grupo.hora == time(9, 0)
    assert grupo.capacidade_max == 12


def test_outro_fisioterapeuta_nao_edita_grupo_alheio(client, app):
    id_admin = id_do_usuario(app, "admin@teste.com")
    id_grupo = criar_grupo(app, id_admin)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert client.get(f"/grupos/{id_grupo}/editar").status_code == 403


def test_editar_mantendo_o_proprio_horario_e_aceito(client, app):
    """O grupo não pode conflitar consigo mesmo ao salvar sem mudar a hora."""
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio, dia_semana=TERCA, hora=time(14, 0))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(
        f"/grupos/{id_grupo}/editar",
        data={
            "nome": "Nome novo",
            "regiao": "OMBRO",
            "dia_semana": str(TERCA),
            "hora": "14:00",
            "capacidade_max": "14",
        },
    )

    assert resposta.status_code == 302
    assert buscar(app, id_grupo).nome == "Nome novo"


def test_grupo_inexistente_da_404(client):
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert client.get("/grupos/9999/editar").status_code == 404


# ----------------------------------------------------------------------
# Desativar e reativar
# ----------------------------------------------------------------------


def test_desativar_e_reativar_grupo(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    client.post(f"/grupos/{id_grupo}/situacao")
    assert buscar(app, id_grupo).ativo is False

    client.post(f"/grupos/{id_grupo}/situacao")
    assert buscar(app, id_grupo).ativo is True


def test_desativar_nao_apaga_o_grupo(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    client.post(f"/grupos/{id_grupo}/situacao")

    assert contar(app) == 1


def test_outro_fisioterapeuta_nao_desativa_grupo_alheio(client, app):
    id_admin = id_do_usuario(app, "admin@teste.com")
    id_grupo = criar_grupo(app, id_admin)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert client.post(f"/grupos/{id_grupo}/situacao").status_code == 403
    assert buscar(app, id_grupo).ativo is True
