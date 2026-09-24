"""A folha impressa precisa se explicar sozinha dentro da pasta do setor.

Quem tira o papel da impressora não tem a tela do lado: o período, o
profissional e a data da impressão têm que estar escritos na folha.
"""

from datetime import date, time

import app as modulo_app
from models import Appointment, Patient, User, db

from tests.conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login


def _paciente_com_sessao(app, dia):
    with app.app_context():
        fisio = db.session.scalar(db.select(User).filter_by(email="fisio@teste.com"))
        paciente = Patient(nome="Joana Ribeiro", fisioterapeuta_id=fisio.id, ativo=True)
        db.session.add(paciente)
        db.session.commit()
        db.session.add(
            Appointment(
                paciente_id=paciente.id,
                fisioterapeuta_id=fisio.id,
                data=dia,
                hora=time(9, 0),
                tipo="SESSAO",
                status="REALIZADO",
            )
        )
        db.session.commit()
        return fisio.id


def test_resumo_impresso_diz_o_periodo_e_a_data_da_impressao(client, app, monkeypatch):
    """A folha não dizia de que período era: o intervalo era no-print."""
    dia = date(2026, 9, 22)
    monkeypatch.setattr(modulo_app, "hoje", lambda: dia)
    _paciente_com_sessao(app, dia)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    html = client.get("/relatorios?periodo=mes&mes=9&ano=2026").get_data(as_text=True)

    inicio = html.find('class="print-only"')
    assert inicio > -1, "a folha não tem o cabeçalho de impressão"
    cabecalho = html[inicio : html.find("</p>", inicio)]
    assert "01/09/2026" in cabecalho
    assert "30/09/2026" in cabecalho
    assert "22/09/2026" in cabecalho


def test_grade_semanal_carimba_o_dia_da_impressao(client, app, monkeypatch):
    """O rodapé carimbava a segunda-feira da semana mostrada, não hoje."""
    hoje = date(2026, 9, 22)
    monkeypatch.setattr(modulo_app, "hoje", lambda: hoje)
    fisio_id = _paciente_com_sessao(app, date(2026, 8, 10))
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    # Uma semana de agosto, bem longe de hoje: as duas datas não se confundem.
    html = client.get(
        f"/agenda/semana?data=2026-08-10&profissional={fisio_id}"
    ).get_data(as_text=True)

    inicio = html.find('class="print-rodape')
    assert inicio > -1, "a grade não tem rodapé de impressão"
    rodape = html[inicio : html.find("</p>", inicio)]
    assert "impresso em 22/09/2026" in rodape
    assert "10/08/2026" in rodape, "o rodapé deve dizer qual semana é"
    assert "Rafael Santos" in rodape, "o rodapé deve dizer de quem é a agenda"


def test_folhas_nao_dependem_mais_do_fundo_de_tela(client, app):
    """O cinza da tela e a altura de 100vh iam junto para o papel.

    Não dá para medir pixel aqui; o que dá para garantir é que a regra de
    impressão continua cobrindo os três seletores que venciam por
    especificidade — foi a falta deles que imprimia uma página em branco.
    """
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    css = client.get("/static/css/style.css").get_data(as_text=True)
    bloco = css[css.find("@media print") :]

    for seletor in (":root,", "  body,", "  body.app-page {"):
        assert seletor in bloco, f"a regra de impressão perdeu {seletor.strip()}"
    assert "min-height: 0" in bloco
