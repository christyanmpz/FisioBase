"""Os rótulos de situação têm que sair todos da mesma tabela.

Duas telas guardavam a própria lista de nomes escrita à mão. Quando a
"Falta justificada" nasceu, essas listas não foram atualizadas e a etiqueta
saía em branco nos dashboards. Aqui cada tela é renderizada de verdade com
um agendamento em cada situação, exigindo o nome certo na tela.
"""

from datetime import time

import pytest

import app as modulo_app
from app import ROTULOS_DE_STATUS
from models import Appointment, Patient, User, db

from tests.conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login


def _cenario(app, status):
    """Cria um paciente com um agendamento de hoje na situação pedida."""
    with app.app_context():
        fisio = db.session.scalar(db.select(User).filter_by(email="fisio@teste.com"))
        paciente = Patient(nome="Joana Ribeiro", fisioterapeuta_id=fisio.id, ativo=True)
        db.session.add(paciente)
        db.session.commit()

        db.session.add(
            Appointment(
                paciente_id=paciente.id,
                fisioterapeuta_id=fisio.id,
                data=modulo_app.hoje(),
                hora=time(9, 0),
                tipo="SESSAO",
                status=status,
            )
        )
        db.session.commit()


def _etiqueta(html):
    """Devolve o texto da etiqueta de situação da linha do paciente."""
    pedaco = html[html.find("Joana Ribeiro") :]
    abre = pedaco.find('<span class="situacao-badge')
    assert abre > -1, "a linha do paciente não trouxe etiqueta de situação"
    inicio = pedaco.find(">", abre) + 1
    return pedaco[inicio : pedaco.find("</span>", inicio)].strip()


@pytest.mark.parametrize("status", sorted(ROTULOS_DE_STATUS))
def test_dashboard_do_fisioterapeuta_nomeia_toda_situacao(client, app, status):
    _cenario(app, status)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    resposta = client.get("/dashboard/fisioterapeuta")

    assert resposta.status_code == 200
    assert _etiqueta(resposta.get_data(as_text=True)) == ROTULOS_DE_STATUS[status]


@pytest.mark.parametrize("status", sorted(ROTULOS_DE_STATUS))
def test_dashboard_do_admin_nomeia_toda_situacao(client, app, status):
    _cenario(app, status)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    resposta = client.get("/dashboard/admin")

    assert resposta.status_code == 200
    assert _etiqueta(resposta.get_data(as_text=True)) == ROTULOS_DE_STATUS[status]


def test_agenda_usa_os_mesmos_nomes_do_resto_do_sistema(client, app):
    """A agenda dizia "Realizado" onde a ficha do paciente diz "Compareceu"."""
    _cenario(app, "AGENDADO")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = client.get(f"/agenda?data={modulo_app.hoje().isoformat()}").get_data(
        as_text=True
    )

    for valor, nome in ROTULOS_DE_STATUS.items():
        assert f'value="{valor}"' in html, f"a agenda não oferece {valor}"
        assert nome in html, f"a agenda não chama {valor} de {nome}"
    assert ">Realizado<" not in html
