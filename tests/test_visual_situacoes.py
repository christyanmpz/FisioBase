"""Cada situação tem a sua cor, e o bloco do grupo não finge ser atendimento.

O sistema tinha só duas cores de etiqueta, herdadas das classes de cargo do
usuário: verde para "Compareceu" e âmbar para todo o resto. Agendado,
Confirmado, Faltou, Falta justificada e Cancelado ficavam idênticos em oito
telas. Aqui cada situação é renderizada de verdade e a classe é conferida.
"""

from datetime import date, time, timedelta

import pytest

import app as modulo_app
from app import CLASSES_DE_CICLO, CLASSES_DE_STATUS
from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from models import Appointment, Group, GroupPatient, Patient, TreatmentCycle, User, db

HOJE = date(2026, 9, 22)


def _fisio(app, email="fisio@teste.com"):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def _paciente_com_agendamento(app, status, tipo="SESSAO", dia=HOJE):
    id_fisio = _fisio(app)
    with app.app_context():
        paciente = Patient(nome="Joana Ribeiro", fisioterapeuta_id=id_fisio, ativo=True)
        db.session.add(paciente)
        db.session.commit()
        db.session.add(
            Appointment(
                paciente_id=paciente.id,
                fisioterapeuta_id=id_fisio,
                data=dia,
                hora=time(9, 0),
                tipo=tipo,
                status=status,
            )
        )
        db.session.commit()
        return paciente.id


def _classe_da_etiqueta(html, ancora="Joana Ribeiro"):
    """Devolve o modificador da etiqueta de situação da linha da âncora."""
    pedaco = html[html.find(ancora) :]
    marca = "situacao-badge situacao-badge--"
    abre = pedaco.find(marca)
    assert abre > -1, "não achei etiqueta de situação nessa linha"
    resto = pedaco[abre + len(marca) :]
    return resto[: resto.find('"')].strip()


# ----------------------------------------------------------------------
# Uma cor por situação
# ----------------------------------------------------------------------


@pytest.mark.parametrize("status", sorted(CLASSES_DE_STATUS))
def test_cada_situacao_tem_a_propria_cor(client, app, monkeypatch, status):
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    _paciente_com_agendamento(app, status)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = client.get("/dashboard/fisioterapeuta").get_data(as_text=True)

    assert _classe_da_etiqueta(html) == CLASSES_DE_STATUS[status]


def test_falta_e_falta_justificada_nao_compartilham_a_cor(client, app, monkeypatch):
    """A justificada conta como atendimento; pintar igual à falta mentiria."""
    assert CLASSES_DE_STATUS["FALTOU"] != CLASSES_DE_STATUS["FALTA_JUSTIFICADA"]
    assert CLASSES_DE_STATUS["FALTOU"] == "faltou"


def test_situacoes_diferentes_nao_caem_na_mesma_classe(client, app):
    """Antes, cinco das seis situações caíam todas em role-badge--admin."""
    usadas = set(CLASSES_DE_STATUS.values())
    assert len(usadas) == len(CLASSES_DE_STATUS), "duas situações com a mesma cor"


def test_ficha_do_paciente_usa_a_cor_da_situacao(client, app, monkeypatch):
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    id_paciente = _paciente_com_agendamento(app, "FALTOU")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = client.get(f"/pacientes/{id_paciente}").get_data(as_text=True)

    assert "situacao-badge--faltou" in html


def test_nenhuma_tela_usa_classe_de_cargo_para_situacao(client, app):
    """A classe de cargo ficou só para o cargo, na lista de usuários."""
    import pathlib

    modelos = pathlib.Path(modulo_app.__file__).parent / "templates"
    culpados = []
    for arquivo in modelos.glob("*.html"):
        if arquivo.name == "usuarios_lista.html":
            continue
        if "role-badge" in arquivo.read_text(encoding="utf-8"):
            culpados.append(arquivo.name)
    assert not culpados, f"ainda usam classe de cargo para situação: {culpados}"


# ----------------------------------------------------------------------
# O bloco do grupo na agenda
# ----------------------------------------------------------------------


def _grupo_com_encontro(app):
    id_fisio = _fisio(app)
    with app.app_context():
        grupo = Group(
            nome="Grupo Coluna manhã",
            regiao="COLUNA",
            fisioterapeuta_id=id_fisio,
            dia_semana=HOJE.weekday(),
            hora=time(8, 0),
            capacidade_max=14,
            total_semanas=6,
            ativo=True,
        )
        db.session.add(grupo)
        db.session.commit()
        db.session.add(
            Appointment(
                grupo_id=grupo.id,
                fisioterapeuta_id=id_fisio,
                data=HOJE,
                hora=time(8, 0),
                tipo="GRUPO",
                duracao_min=60,
                status="AGENDADO",
            )
        )
        db.session.commit()
        return grupo.id


def test_bloco_do_grupo_leva_para_a_lista_de_presenca(client, app, monkeypatch):
    """Ali ficava um campo de situação que nenhuma conta do sistema lia."""
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    id_grupo = _grupo_com_encontro(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = client.get(f"/agenda?data={HOJE.isoformat()}").get_data(as_text=True)

    linha = html[html.find("Grupo Coluna manhã") :]
    linha = linha[: linha.find("</tr>")]
    assert f"/grupos/{id_grupo}/presenca" in linha
    assert "<select" not in linha, "o bloco do grupo não deve oferecer situação"


def test_sessao_individual_continua_com_o_campo_de_situacao(client, app, monkeypatch):
    """A mudança é só do bloco de grupo: a sessão normal não pode perder nada."""
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    _paciente_com_agendamento(app, "AGENDADO")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = client.get(f"/agenda?data={HOJE.isoformat()}").get_data(as_text=True)

    linha = html[html.find("Joana Ribeiro") :]
    linha = linha[: linha.find("</tr>")]
    assert "<select" in linha
    assert 'value="FALTA_JUSTIFICADA"' in linha


def test_agenda_diferencia_grupo_de_sessao(client, app, monkeypatch):
    """O bloco de grupo usava a mesma cor da sessão individual."""
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    _grupo_com_encontro(app)
    _paciente_com_agendamento(app, "AGENDADO")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = client.get(f"/agenda?data={HOJE.isoformat()}").get_data(as_text=True)

    assert "tipo-badge--grupo" in html
    assert "tipo-badge--sessao" in html


# ----------------------------------------------------------------------
# Situação do ciclo
# ----------------------------------------------------------------------


@pytest.mark.parametrize("status", sorted(CLASSES_DE_CICLO))
def test_ciclo_tambem_tem_cor_por_situacao(client, app, monkeypatch, status):
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    id_fisio = _fisio(app)
    with app.app_context():
        paciente = Patient(nome="Joana Ribeiro", fisioterapeuta_id=id_fisio, ativo=True)
        db.session.add(paciente)
        db.session.commit()
        id_paciente = paciente.id
        db.session.add(
            TreatmentCycle(
                paciente_id=id_paciente,
                fisioterapeuta_id=id_fisio,
                regiao="coluna",
                modalidade="INDIVIDUAL",
                data_avaliacao=HOJE - timedelta(days=30),
                total_sessoes=10,
                status=status,
            )
        )
        db.session.commit()

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    html = client.get(f"/pacientes/{id_paciente}/ciclos").get_data(as_text=True)

    assert f"situacao-badge--{CLASSES_DE_CICLO[status]}" in html
