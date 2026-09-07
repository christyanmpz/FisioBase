"""Testes de autenticação e controle de acesso por perfil."""

from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login


def test_login_com_credenciais_validas_leva_ao_painel_admin(client):
    resposta = fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    assert resposta.status_code == 200
    assert "Painel do administrador" in resposta.get_data(as_text=True)


def test_login_com_credenciais_validas_leva_ao_painel_fisioterapeuta(client):
    resposta = fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    assert resposta.status_code == 200
    assert "/dashboard/fisioterapeuta" in resposta.get_data(as_text=True)


def test_login_com_senha_incorreta_e_recusado(client):
    resposta = client.post(
        "/login", data={"email": "admin@teste.com", "senha": "senha-errada"}
    )
    assert resposta.status_code == 401


def test_login_com_email_inexistente_e_recusado(client):
    resposta = client.post(
        "/login", data={"email": "ninguem@teste.com", "senha": SENHA_ADMIN}
    )
    assert resposta.status_code == 401


def test_email_e_normalizado_para_minusculas(client):
    resposta = fazer_login(client, "  ADMIN@TESTE.COM  ", SENHA_ADMIN)
    assert resposta.status_code == 200
    assert "Painel do administrador" in resposta.get_data(as_text=True)


def test_dashboard_exige_autenticacao(client):
    resposta = client.get("/dashboard/admin")
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_fisioterapeuta_nao_acessa_area_administrativa(client):
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.get("/dashboard/admin")
    assert resposta.status_code == 403


def test_admin_nao_acessa_painel_do_fisioterapeuta(client):
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    resposta = client.get("/dashboard/fisioterapeuta")
    assert resposta.status_code == 403


def test_logout_encerra_a_sessao(client):
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    client.post("/logout")
    resposta = client.get("/dashboard/admin")
    assert resposta.status_code == 302


def test_rota_inexistente_devolve_404(client):
    assert client.get("/rota-que-nao-existe").status_code == 404


def test_usuario_desativado_nao_consegue_entrar(client, app):
    from conftest import criar_usuario
    from models import PHYSIOTHERAPIST_PROFILE, db

    with app.app_context():
        db.session.add(
            criar_usuario(
                "Inativo",
                "inativo@teste.com",
                "Senha@123",
                PHYSIOTHERAPIST_PROFILE,
                ativo=False,
            )
        )
        db.session.commit()

    resposta = client.post(
        "/login", data={"email": "inativo@teste.com", "senha": "Senha@123"}
    )
    assert resposta.status_code == 401
