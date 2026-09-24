"""A string de conexão precisa dizer qual driver usar.

Em 24/09/2026 a produção caiu inteira com `ModuleNotFoundError: No module
named 'psycopg'`. Nenhuma linha de código de negócio tinha mudado: o
SQLAlchemy 2.1 trocou o driver padrão de `postgresql://` de psycopg2 para
psycopg (versão 3), o requirements.txt não fixava a versão, e uma publicação
qualquer bastou para o Vercel trazer a versão nova.

Estes testes travam as duas pontas: a string de conexão diz o driver, e o
requirements.txt fixa a versão.
"""

import pathlib
import re

import pytest

import app as modulo_app
from app import _com_driver_explicito

RAIZ = pathlib.Path(modulo_app.__file__).parent


@pytest.mark.parametrize(
    "entrada",
    [
        "postgresql://usuario:senha@host:6543/postgres",
        "postgres://usuario:senha@host:6543/postgres",
    ],
)
def test_a_conexao_diz_qual_driver_usar(entrada):
    """Sem isto, quem escolhe o driver é a versão do SQLAlchemy do dia."""
    saida = _com_driver_explicito(entrada)

    assert saida.startswith("postgresql+psycopg2://")
    assert saida.endswith("usuario:senha@host:6543/postgres")


def test_o_driver_escolhido_e_o_que_esta_instalado():
    """O driver da string tem que ser o pacote que o requirements instala."""
    from sqlalchemy.engine.url import make_url

    url = make_url(_com_driver_explicito("postgresql://u:p@h:6543/d"))

    assert url.get_dialect().driver == "psycopg2"


def test_nao_estraga_uma_conexao_que_ja_traz_o_driver():
    ja_explicita = "postgresql+psycopg2://u:p@h:6543/d"
    assert _com_driver_explicito(ja_explicita) == ja_explicita


def test_nao_mexe_no_sqlite_dos_testes():
    assert _com_driver_explicito("sqlite:///:memory:") == "sqlite:///:memory:"


def test_a_versao_do_sqlalchemy_esta_fixada():
    """Foi a falta desta linha que derrubou a produção."""
    texto = (RAIZ / "requirements.txt").read_text(encoding="utf-8")
    achado = re.search(r"^SQLAlchemy==(\d+)\.(\d+)", texto, re.M)

    assert achado, "o requirements.txt voltou a não fixar o SQLAlchemy"
    maior, menor = int(achado.group(1)), int(achado.group(2))
    assert (maior, menor) == (2, 0), (
        "o SQLAlchemy saiu da faixa 2.0. A 2.1 usa psycopg (versão 3) por "
        "padrão: trocar exige instalar psycopg[binary] no lugar do "
        "psycopg2-binary"
    )


def test_o_driver_do_requirements_bate_com_o_da_conexao():
    texto = (RAIZ / "requirements.txt").read_text(encoding="utf-8")
    assert "psycopg2-binary" in texto
    assert "+psycopg2://" in (RAIZ / "app.py").read_text(encoding="utf-8")
