"""Resumo numérico do relatório e os filtros de semana, mês e ano.

A clínica soma isso na mão hoje: sessões e triagens separadas, falta
justificada contando como atendimento, e a somatória do ano no fim.
"""

import re
from datetime import date, time, timedelta

import app as modulo_app
from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from models import Appointment, Patient, User, db

# 14/09/2026 é uma segunda-feira.
SEGUNDA = date(2026, 9, 14)


def fixar_hoje(monkeypatch, dia=SEGUNDA):
    monkeypatch.setattr(modulo_app, "hoje", lambda: dia)


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def agendar(app, fisioterapeuta_id, tipo, status, dia, hora=time(9, 0)):
    with app.app_context():
        paciente = db.session.scalar(db.select(Patient))
        if paciente is None:
            paciente = Patient(
                nome="Paciente Teste",
                fisioterapeuta_id=fisioterapeuta_id,
                ativo=True,
            )
            db.session.add(paciente)
            db.session.flush()

        db.session.add(
            Appointment(
                tipo=tipo,
                paciente_id=paciente.id,
                fisioterapeuta_id=fisioterapeuta_id,
                data=dia,
                hora=hora,
                duracao_min=30,
                status=status,
            )
        )
        db.session.commit()


def abrir(client, **filtros):
    query = "&".join(f"{chave}={valor}" for chave, valor in filtros.items())
    resposta = client.get(f"/relatorios?{query}")
    assert resposta.status_code == 200
    return resposta.get_data(as_text=True)


def linha_do_resumo(pagina, titulo):
    """Lê uma linha da tabela do resumo como (realizados, faltas, no ano)."""
    inicio = pagina.index(f">{titulo}<")
    trecho = pagina[inicio : pagina.index("</tr>", inicio)]
    celulas = [
        re.sub(r"<[^>]+>", "", celula).strip()
        for celula in re.findall(r"<td.*?</td>", trecho, re.S)
    ]
    assert len(celulas) == 3, f"linha inesperada: {celulas}"
    return tuple(int(c) for c in celulas)


# ----------------------------------------------------------------------
# Os números
# ----------------------------------------------------------------------


def test_separa_sessoes_de_triagens(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    agendar(app, id_fisio, "SESSAO", "REALIZADO", SEGUNDA)
    agendar(app, id_fisio, "SESSAO", "REALIZADO", SEGUNDA, time(9, 30))
    agendar(app, id_fisio, "AVALIACAO", "REALIZADO", SEGUNDA, time(10, 0))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = abrir(client, periodo="mes", mes=9, ano=2026)

    assert linha_do_resumo(pagina, "Sessões (individuais e grupo)")[0] == 2
    assert linha_do_resumo(pagina, "Avaliações / triagens")[0] == 1
    assert linha_do_resumo(pagina, "Total de atendimentos")[0] == 3


def test_falta_justificada_conta_como_atendimento(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    agendar(app, id_fisio, "SESSAO", "REALIZADO", SEGUNDA)
    agendar(app, id_fisio, "SESSAO", "FALTA_JUSTIFICADA", SEGUNDA, time(9, 30))
    agendar(app, id_fisio, "SESSAO", "FALTOU", SEGUNDA, time(10, 0))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    realizados, faltas, _ = linha_do_resumo(
        abrir(client, periodo="mes", mes=9, ano=2026),
        "Sessões (individuais e grupo)",
    )

    # 2 atendimentos (compareceu + justificada) e 1 falta não avisada.
    assert (realizados, faltas) == (2, 1)


def test_cancelado_nao_entra_em_atendimento_nem_em_falta(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    agendar(app, id_fisio, "SESSAO", "CANCELADO", SEGUNDA)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    realizados, faltas, _ = linha_do_resumo(
        abrir(client, periodo="mes", mes=9, ano=2026), "Total de atendimentos"
    )

    assert (realizados, faltas) == (0, 0)


# ----------------------------------------------------------------------
# Os filtros
# ----------------------------------------------------------------------


def test_filtro_semanal_pega_so_a_semana(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    agendar(app, id_fisio, "SESSAO", "REALIZADO", SEGUNDA)
    agendar(app, id_fisio, "SESSAO", "REALIZADO", SEGUNDA + timedelta(days=4))
    # Segunda seguinte: fora da semana escolhida.
    agendar(app, id_fisio, "SESSAO", "REALIZADO", SEGUNDA + timedelta(days=7))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = abrir(client, periodo="semana", data=SEGUNDA.isoformat())

    assert linha_do_resumo(pagina, "Total de atendimentos")[0] == 2
    # O rótulo mostra a semana cheia; a clínica não atende no fim de semana.
    assert "Semana de 14/09 a 20/09/2026" in pagina


def test_semana_comeca_na_segunda_mesmo_escolhendo_uma_quarta(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    agendar(app, id_fisio, "SESSAO", "REALIZADO", SEGUNDA)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    quarta = (SEGUNDA + timedelta(days=2)).isoformat()
    pagina = abrir(client, periodo="semana", data=quarta)

    assert linha_do_resumo(pagina, "Total de atendimentos")[0] == 1


def test_filtro_anual_soma_o_ano_inteiro(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    agendar(app, id_fisio, "SESSAO", "REALIZADO", date(2026, 2, 10))
    agendar(app, id_fisio, "SESSAO", "REALIZADO", date(2026, 7, 8))
    agendar(app, id_fisio, "SESSAO", "REALIZADO", date(2025, 11, 4))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = abrir(client, periodo="ano", ano=2026)

    assert linha_do_resumo(pagina, "Total de atendimentos")[0] == 2
    assert "Ano de 2026" in pagina


def test_coluna_anual_aparece_mesmo_no_filtro_mensal(client, app, monkeypatch):
    """O setor fecha o ano somando os meses; a somatória vem junto."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    agendar(app, id_fisio, "SESSAO", "REALIZADO", date(2026, 9, 14))
    agendar(app, id_fisio, "SESSAO", "REALIZADO", date(2026, 3, 2))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    pagina = abrir(client, periodo="mes", mes=9, ano=2026)
    realizados, _, no_ano = linha_do_resumo(pagina, "Total de atendimentos")

    assert "No ano de 2026" in pagina
    # 1 no mês de setembro, 2 no ano.
    assert (realizados, no_ano) == (1, 2)


def test_periodo_invalido_cai_no_mensal(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    pagina = abrir(client, periodo="decada")

    assert "Setembro de 2026" in pagina


def test_fisioterapeuta_ve_so_os_proprios_numeros(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_admin = id_do_usuario(app, "admin@teste.com")
    agendar(app, id_fisio, "SESSAO", "REALIZADO", SEGUNDA)
    agendar(app, id_admin, "SESSAO", "REALIZADO", SEGUNDA, time(9, 30))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    assert (
        linha_do_resumo(
            abrir(client, periodo="mes", mes=9, ano=2026), "Total de atendimentos"
        )[0]
        == 1
    )
