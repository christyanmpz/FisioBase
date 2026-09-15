"""Paginação da lista de pacientes."""

import app as modulo_app
from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from models import Patient, User, db

POR_PAGINA = modulo_app.PACIENTES_POR_PAGINA


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def criar_pacientes(app, fisioterapeuta_id, quantidade, prefixo="Paciente"):
    """Cria pacientes numerados; o nome define a ordem da listagem."""
    with app.app_context():
        for numero in range(1, quantidade + 1):
            db.session.add(
                Patient(
                    nome=f"{prefixo} {numero:03d}",
                    fisioterapeuta_id=fisioterapeuta_id,
                    ativo=True,
                )
            )
        db.session.commit()


def test_primeira_pagina_traz_o_limite_de_registros(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_pacientes(app, id_fisio, POR_PAGINA + 5)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/pacientes").get_data(as_text=True)

    assert "Paciente 001" in corpo
    assert f"Paciente {POR_PAGINA:03d}" in corpo
    assert f"Paciente {POR_PAGINA + 1:03d}" not in corpo


def test_segunda_pagina_traz_o_restante(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_pacientes(app, id_fisio, POR_PAGINA + 5)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/pacientes?pagina=2").get_data(as_text=True)

    assert f"Paciente {POR_PAGINA + 1:03d}" in corpo
    assert "Paciente 001" not in corpo


def test_lista_curta_nao_mostra_navegacao(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_pacientes(app, id_fisio, 3)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/pacientes").get_data(as_text=True)

    assert "Paginação dos pacientes" not in corpo
    assert "3 registros" in corpo


def test_lista_longa_mostra_navegacao_e_total(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_pacientes(app, id_fisio, POR_PAGINA + 5)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/pacientes").get_data(as_text=True)

    assert "Paginação dos pacientes" in corpo
    assert f"{POR_PAGINA + 5} registros" in corpo
    assert "página 1 de 2" in corpo


def test_busca_continua_valendo_entre_paginas(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_pacientes(app, id_fisio, POR_PAGINA + 5, prefixo="Ana")
    criar_pacientes(app, id_fisio, 3, prefixo="Bruno")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/pacientes?q=Ana&pagina=2").get_data(as_text=True)

    assert "Bruno" not in corpo
    assert f"Ana {POR_PAGINA + 1:03d}" in corpo
    assert "q=Ana" in corpo


def test_pagina_alem_do_fim_nao_quebra(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_pacientes(app, id_fisio, 3)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.get("/pacientes?pagina=99")

    assert resposta.status_code == 200


def test_pagina_invalida_volta_para_a_primeira(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    criar_pacientes(app, id_fisio, POR_PAGINA + 5)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/pacientes?pagina=abc").get_data(as_text=True)

    assert "Paciente 001" in corpo


def test_paginacao_respeita_o_escopo_do_fisioterapeuta(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_admin = id_do_usuario(app, "admin@teste.com")
    criar_pacientes(app, id_fisio, 3, prefixo="Meu")
    criar_pacientes(app, id_admin, POR_PAGINA + 5, prefixo="Outro")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/pacientes").get_data(as_text=True)

    assert "3 registros" in corpo
    assert "Outro" not in corpo


def test_admin_pagina_a_clinica_inteira(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_admin = id_do_usuario(app, "admin@teste.com")
    criar_pacientes(app, id_fisio, 12, prefixo="Ana")
    criar_pacientes(app, id_admin, 12, prefixo="Bruno")

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    corpo = client.get("/pacientes").get_data(as_text=True)

    assert "24 registros" in corpo
    assert "página 1 de 2" in corpo
