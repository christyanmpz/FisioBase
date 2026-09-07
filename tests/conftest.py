"""Configuração compartilhada dos testes.

Os testes rodam sempre em SQLite na memória: nenhuma conexão é aberta
contra o PostgreSQL do Supabase e nenhum dado real é tocado.
"""

import pytest

from app import create_app
from models import ADMIN_PROFILE, PHYSIOTHERAPIST_PROFILE, User, db

SENHA_ADMIN = "Admin@123"
SENHA_FISIO = "Fisio@123"


@pytest.fixture
def app():
    aplicacao = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "chave-de-teste",
            "WTF_CSRF_ENABLED": False,
        }
    )

    with aplicacao.app_context():
        db.create_all()
        db.session.add_all(
            [
                criar_usuario(
                    "Marina Almeida", "admin@teste.com", SENHA_ADMIN, ADMIN_PROFILE
                ),
                criar_usuario(
                    "Rafael Santos",
                    "fisio@teste.com",
                    SENHA_FISIO,
                    PHYSIOTHERAPIST_PROFILE,
                ),
            ]
        )
        db.session.commit()

    yield aplicacao

    with aplicacao.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def criar_usuario(nome, email, senha, perfil, ativo=True):
    usuario = User(nome=nome, email=email, perfil=perfil, ativo=ativo, falhas_login=0)
    usuario.set_password(senha)
    return usuario


def fazer_login(client, email, senha):
    """Autentica pelo formulário HTML e devolve a resposta."""
    return client.post(
        "/login",
        data={"email": email, "senha": senha},
        follow_redirects=True,
    )
