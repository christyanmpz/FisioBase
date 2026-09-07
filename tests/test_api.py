"""Testes dos endpoints JSON consumidos pelo front React."""

from conftest import SENHA_ADMIN, SENHA_FISIO


def login_api(client, email, senha):
    return client.post("/api/auth/login", json={"email": email, "senha": senha})


def test_api_login_valido_devolve_usuario_e_destino(client):
    resposta = login_api(client, "admin@teste.com", SENHA_ADMIN)
    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["authenticated"] is True
    assert corpo["user"]["perfil"] == "ADMIN"
    assert corpo["redirect_path"] == "/dashboard/admin"


def test_api_login_nunca_expoe_o_hash_da_senha(client):
    corpo = login_api(client, "admin@teste.com", SENHA_ADMIN).get_json()
    assert "senha_hash" not in corpo["user"]
    assert "senha" not in corpo["user"]


def test_api_login_invalido_devolve_401(client):
    resposta = login_api(client, "admin@teste.com", "senha-errada")
    assert resposta.status_code == 401
    assert resposta.get_json()["authenticated"] is False


def test_api_session_sem_login_nao_identifica_usuario(client):
    corpo = client.get("/api/auth/session").get_json()
    assert corpo["authenticated"] is False
    assert corpo["user"] is None


def test_api_session_reconhece_o_cookie_apos_login(client):
    login_api(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get("/api/auth/session").get_json()
    assert corpo["authenticated"] is True
    assert corpo["user"]["email"] == "fisio@teste.com"


def test_api_logout_encerra_a_sessao(client):
    login_api(client, "admin@teste.com", SENHA_ADMIN)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/session").get_json()["authenticated"] is False


def test_api_admin_users_bloqueia_fisioterapeuta(client):
    login_api(client, "fisio@teste.com", SENHA_FISIO)
    assert client.get("/api/admin/users").status_code == 403


def test_api_admin_users_lista_totais_para_admin(client):
    login_api(client, "admin@teste.com", SENHA_ADMIN)
    corpo = client.get("/api/admin/users").get_json()
    assert corpo["totals"]["users"] == 2
    assert corpo["totals"]["admins"] == 1
    assert corpo["totals"]["fisioterapeutas"] == 1
