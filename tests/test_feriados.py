"""Importação dos feriados nacionais da BrasilAPI.

A tabela `feriados` existia desde o esquema original e cinco partes do
sistema pulam essas datas, mas não havia como cadastrar um feriado a não ser
rodando SQL no banco. Esta é a tela que fecha esse buraco.

Nenhum teste aqui toca a internet: a função que baixa a página é trocada por
uma simulada. É ela, e só ela, que fala com a rede no código de verdade.
"""

import json
import urllib.error
from datetime import date, time

import pytest

import app as modulo_app
import integracoes
from conftest import SENHA_ADMIN, SENHA_FISIO, fazer_login
from integracoes import IntegracaoIndisponivel, buscar_feriados_nacionais
from models import Appointment, Holiday, Patient, TreatmentCycle, User, db

HOJE = date(2026, 9, 24)

# Um recorte do que a BrasilAPI devolve de verdade.
RESPOSTA_DA_API = [
    {"date": "2027-01-01", "name": "Confraternização mundial", "type": "national"},
    {"date": "2027-04-21", "name": "Tiradentes", "type": "national"},
    {"date": "2027-05-01", "name": "Dia do trabalho", "type": "national"},
    {"date": "2027-09-07", "name": "Independência do Brasil", "type": "national"},
    {"date": "2027-12-25", "name": "Natal", "type": "national"},
]


def simular_api(monkeypatch, conteudo=RESPOSTA_DA_API):
    """Faz a BrasilAPI responder o que o teste quiser, sem sair da máquina."""
    monkeypatch.setattr(
        integracoes, "_baixar", lambda url: json.dumps(conteudo).encode("utf-8")
    )


def simular_api_fora_do_ar(monkeypatch, erro=None):
    def explodir(url):
        raise erro or urllib.error.URLError("sem rede")

    monkeypatch.setattr(integracoes, "_baixar", explodir)


def importar(client, ano=2027):
    return client.post(
        "/feriados/importar", data={"ano": str(ano)}, follow_redirects=True
    )


def feriados_no_banco(app):
    with app.app_context():
        return Holiday.query.order_by(Holiday.data).all()


# ----------------------------------------------------------------------
# O cliente da API, sozinho
# ----------------------------------------------------------------------


def test_traduz_a_resposta_para_o_formato_do_sistema(monkeypatch):
    simular_api(monkeypatch)

    feriados = buscar_feriados_nacionais(2027)

    assert len(feriados) == 5
    assert feriados[0] == {"data": date(2027, 1, 1), "nome": "Confraternização mundial"}
    assert feriados[-1] == {"data": date(2027, 12, 25), "nome": "Natal"}
    assert feriados == sorted(feriados, key=lambda f: f["data"])


def test_api_fora_do_ar_vira_erro_com_nome(monkeypatch):
    simular_api_fora_do_ar(monkeypatch)

    with pytest.raises(IntegracaoIndisponivel):
        buscar_feriados_nacionais(2027)


def test_resposta_que_nao_e_json_nao_derruba_o_sistema(monkeypatch):
    monkeypatch.setattr(integracoes, "_baixar", lambda url: b"<html>erro 502</html>")

    with pytest.raises(IntegracaoIndisponivel):
        buscar_feriados_nacionais(2027)


def test_erro_http_da_api_vira_erro_com_nome(monkeypatch):
    simular_api_fora_do_ar(
        monkeypatch,
        urllib.error.HTTPError("url", 503, "indisponível", {}, None),
    )

    with pytest.raises(IntegracaoIndisponivel):
        buscar_feriados_nacionais(2027)


def test_data_estranha_no_meio_nao_invalida_as_outras(monkeypatch):
    """Uma linha torta da API não pode custar o ano inteiro."""
    simular_api(
        monkeypatch,
        [
            {"date": "2027-04-21", "name": "Tiradentes", "type": "national"},
            {"date": "trinta de maio", "name": "Quebrado", "type": "national"},
            {"date": "2027-12-25", "name": "Natal", "type": "national"},
            {"name": "Sem data", "type": "national"},
        ],
    )

    feriados = buscar_feriados_nacionais(2027)

    assert [f["nome"] for f in feriados] == ["Tiradentes", "Natal"]


def test_ano_fora_do_intervalo_nem_chega_a_consultar(monkeypatch):
    def nao_deveria_ser_chamado(url):
        raise AssertionError("não era para consultar a API com ano inválido")

    monkeypatch.setattr(integracoes, "_baixar", nao_deveria_ser_chamado)

    with pytest.raises(ValueError):
        buscar_feriados_nacionais(1500)


def test_nenhum_dado_de_paciente_sai_na_consulta(monkeypatch):
    """A única coisa enviada para fora é o ano."""
    visitadas = []
    monkeypatch.setattr(
        integracoes,
        "_baixar",
        lambda url: visitadas.append(url)
        or json.dumps(RESPOSTA_DA_API).encode("utf-8"),
    )

    buscar_feriados_nacionais(2027)

    assert visitadas == ["https://brasilapi.com.br/api/feriados/v1/2027"]


# ----------------------------------------------------------------------
# A tela
# ----------------------------------------------------------------------


def test_administrador_importa_o_ano_inteiro(client, app, monkeypatch):
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    simular_api(monkeypatch)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    resposta = importar(client)
    html = resposta.get_data(as_text=True)

    assert resposta.status_code == 200
    assert "5 feriado(s) de 2027 importado(s)" in html
    guardados = feriados_no_banco(app)
    assert len(guardados) == 5
    assert all(f.tipo == "NACIONAL" for f in guardados)
    assert guardados[0].nome == "Confraternização mundial"


def test_importar_o_mesmo_ano_de_novo_nao_duplica(client, app, monkeypatch):
    """A coluna `data` é única no banco: sem a conferência isso estouraria."""
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    simular_api(monkeypatch)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    importar(client)
    html = importar(client).get_data(as_text=True)

    assert len(feriados_no_banco(app)) == 5
    assert "já estavam cadastrados" in html


def test_importacao_parcial_completa_o_que_falta(client, app, monkeypatch):
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    with app.app_context():
        db.session.add(Holiday(data=date(2027, 12, 25), nome="Natal", tipo="NACIONAL"))
        db.session.commit()

    simular_api(monkeypatch)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    html = importar(client).get_data(as_text=True)

    assert len(feriados_no_banco(app)) == 5
    assert "4 feriado(s) de 2027 importado(s)" in html
    assert "1 já estava(m) cadastrado(s)" in html


def test_api_fora_do_ar_avisa_e_nao_apaga_nada(client, app, monkeypatch):
    """O resto do sistema não pode parar porque um serviço de fora caiu."""
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    with app.app_context():
        db.session.add(Holiday(data=date(2026, 12, 25), nome="Natal", tipo="NACIONAL"))
        db.session.commit()

    simular_api_fora_do_ar(monkeypatch)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    resposta = importar(client)
    html = resposta.get_data(as_text=True)

    assert resposta.status_code == 200
    assert "continuam valendo" in html
    assert len(feriados_no_banco(app)) == 1, "o que já estava não pode sumir"


def test_ano_invalido_no_formulario(client, app, monkeypatch):
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    html = client.post(
        "/feriados/importar", data={"ano": "abacaxi"}, follow_redirects=True
    ).get_data(as_text=True)

    assert "Informe um ano válido" in html
    assert feriados_no_banco(app) == []


def test_fisioterapeuta_nao_entra_na_tela(client, app, monkeypatch):
    """Feriado vale para a clínica inteira: é configuração de administrador."""
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert client.get("/feriados").status_code == 403
    assert client.post("/feriados/importar", data={"ano": "2027"}).status_code == 403


def test_tela_lista_os_feriados_por_ano(client, app, monkeypatch):
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    with app.app_context():
        db.session.add_all(
            [
                Holiday(data=date(2026, 12, 25), nome="Natal", tipo="NACIONAL"),
                Holiday(data=date(2027, 4, 21), nome="Tiradentes", tipo="NACIONAL"),
                Holiday(
                    data=date(2026, 6, 13),
                    nome="Santo Antônio",
                    tipo="MUNICIPAL",
                ),
            ]
        )
        db.session.commit()

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    html = client.get("/feriados").get_data(as_text=True)

    assert "Tiradentes" in html and "Natal" in html and "Santo Antônio" in html
    assert "3 registros" in html
    # O ano mais recente vem primeiro.
    assert html.find("2027") < html.find("Santo Antônio")


def test_remover_feriado_nao_mexe_em_agendamento(client, app, monkeypatch):
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    with app.app_context():
        fisio = db.session.scalar(db.select(User).filter_by(email="fisio@teste.com"))
        feriado = Holiday(data=date(2026, 12, 25), nome="Natal", tipo="NACIONAL")
        paciente = Patient(nome="Joana Ribeiro", fisioterapeuta_id=fisio.id, ativo=True)
        db.session.add_all([feriado, paciente])
        db.session.commit()
        id_feriado = feriado.id
        db.session.add(
            Appointment(
                paciente_id=paciente.id,
                fisioterapeuta_id=fisio.id,
                data=date(2026, 12, 25),
                hora=time(9, 0),
                tipo="SESSAO",
                status="AGENDADO",
            )
        )
        db.session.commit()

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    html = client.post(
        f"/feriados/{id_feriado}/remover", follow_redirects=True
    ).get_data(as_text=True)

    assert "Feriado removido" in html
    assert feriados_no_banco(app) == []
    with app.app_context():
        assert Appointment.query.count() == 1, "o agendamento não podia sumir"


# ----------------------------------------------------------------------
# O efeito na agenda: é para isso que o feriado serve
# ----------------------------------------------------------------------


def test_feriado_importado_passa_a_ser_pulado_ao_gerar_sessoes(
    client, app, monkeypatch
):
    """O teste que liga a integração ao motivo de ela existir."""
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    # 25/12/2026 é uma sexta-feira.
    natal = date(2026, 12, 25)
    assert natal.weekday() == 4

    with app.app_context():
        fisio = db.session.scalar(db.select(User).filter_by(email="fisio@teste.com"))
        paciente = Patient(nome="Joana Ribeiro", fisioterapeuta_id=fisio.id, ativo=True)
        db.session.add(paciente)
        db.session.commit()
        ciclo = TreatmentCycle(
            paciente_id=paciente.id,
            fisioterapeuta_id=fisio.id,
            regiao="coluna",
            modalidade="INDIVIDUAL",
            data_avaliacao=HOJE,
            total_sessoes=4,
            status="ATIVO",
        )
        db.session.add(ciclo)
        db.session.commit()
        id_ciclo = ciclo.id

    simular_api(
        monkeypatch,
        [{"date": "2026-12-25", "name": "Natal", "type": "national"}],
    )
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    importar(client, ano=2026)

    # Quatro sextas seguidas a partir de 18/12: a de 25/12 tem que ser pulada.
    client.post(
        f"/ciclos/{id_ciclo}/sessoes",
        data={
            "inicio": "2026-12-18",
            "dias": "4",
            "hora": "09:00",
            "quantidade": "4",
        },
        follow_redirects=True,
    )

    with app.app_context():
        datas = [
            a.data
            for a in Appointment.query.filter_by(ciclo_id=id_ciclo, tipo="SESSAO").all()
        ]
    assert datas, "nenhuma sessão foi gerada"
    assert natal not in datas, "a sessão caiu no Natal, o feriado não foi pulado"


# ----------------------------------------------------------------------
# Cadastro à mão: ponto facultativo, feriado da cidade e emenda
# ----------------------------------------------------------------------


def cadastrar(client, data, nome, tipo="FACULTATIVO"):
    return client.post(
        "/feriados",
        data={"data": data, "nome": nome, "tipo": tipo},
        follow_redirects=True,
    )


def test_cadastra_ponto_facultativo_que_a_api_nao_traz(client, app, monkeypatch):
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    html = cadastrar(client, "2026-10-28", "Dia do servidor público").get_data(
        as_text=True
    )

    assert "cadastrado em 28/10/2026" in html
    guardados = feriados_no_banco(app)
    assert len(guardados) == 1
    assert guardados[0].tipo == "FACULTATIVO"
    assert guardados[0].nome == "Dia do servidor público"


def test_a_emenda_e_remover_uma_data_e_cadastrar_outra(client, app, monkeypatch):
    """O caso da secretaria: o 28/10 vira 26/10 para juntar com o fim de semana."""
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    cadastrar(client, "2026-10-28", "Dia do servidor público")
    with app.app_context():
        id_antigo = db.session.scalar(
            db.select(Holiday).where(Holiday.data == date(2026, 10, 28))
        ).id

    client.post(f"/feriados/{id_antigo}/remover", follow_redirects=True)
    cadastrar(client, "2026-10-26", "Dia do servidor público (emenda)")

    datas = [f.data for f in feriados_no_banco(app)]
    assert datas == [date(2026, 10, 26)]


def test_avisa_quando_o_dia_ja_tem_atendimento_marcado(client, app, monkeypatch):
    """Cadastrar o feriado não desmarca ninguém — a tela precisa dizer isso."""
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    dia = date(2026, 10, 26)
    with app.app_context():
        fisio = db.session.scalar(db.select(User).filter_by(email="fisio@teste.com"))
        paciente = Patient(nome="Joana Ribeiro", fisioterapeuta_id=fisio.id, ativo=True)
        db.session.add(paciente)
        db.session.commit()
        for hora in (time(8, 0), time(9, 0)):
            db.session.add(
                Appointment(
                    paciente_id=paciente.id,
                    fisioterapeuta_id=fisio.id,
                    data=dia,
                    hora=hora,
                    tipo="SESSAO",
                    status="AGENDADO",
                )
            )
        db.session.commit()

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    html = cadastrar(client, dia.isoformat(), "Emenda do servidor").get_data(
        as_text=True
    )

    assert "já existem 2 atendimento(s)" in html
    assert "não desmarca ninguém" in html
    with app.app_context():
        assert Appointment.query.count() == 2, "nenhum atendimento podia ser tocado"


def test_cancelado_nao_entra_na_contagem_do_aviso(client, app, monkeypatch):
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    dia = date(2026, 10, 26)
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
                hora=time(8, 0),
                tipo="SESSAO",
                status="CANCELADO",
            )
        )
        db.session.commit()

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    html = cadastrar(client, dia.isoformat(), "Emenda do servidor").get_data(
        as_text=True
    )

    assert "A agenda passa a pular essa data" in html
    assert "já existem" not in html


def test_nao_deixa_cadastrar_a_mesma_data_duas_vezes(client, app, monkeypatch):
    """A coluna `data` é única no banco; o aviso tem que vir antes do erro."""
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    cadastrar(client, "2026-10-26", "Emenda do servidor")
    html = cadastrar(client, "2026-10-26", "Outro nome qualquer").get_data(as_text=True)

    assert "já está cadastrado como Emenda do servidor" in html
    assert len(feriados_no_banco(app)) == 1


@pytest.mark.parametrize(
    "campos, esperado",
    [
        ({"data": "", "nome": "Emenda"}, "data válida"),
        ({"data": "26/10/2026", "nome": "Emenda"}, "data válida"),
        ({"data": "2026-10-26", "nome": "   "}, "Informe o nome"),
        ({"data": "2026-10-26", "nome": "Emenda", "tipo": "CARNAVAL"}, "inválido"),
    ],
)
def test_recusa_cadastro_incompleto(client, app, monkeypatch, campos, esperado):
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    dados = {"tipo": "FACULTATIVO"}
    dados.update(campos)

    html = client.post("/feriados", data=dados, follow_redirects=True).get_data(
        as_text=True
    )

    assert esperado in html
    assert feriados_no_banco(app) == []


def test_fisioterapeuta_nao_cadastra_feriado(client, app, monkeypatch):
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    resposta = client.post(
        "/feriados",
        data={"data": "2026-10-26", "nome": "Emenda", "tipo": "FACULTATIVO"},
    )

    assert resposta.status_code == 403
    assert feriados_no_banco(app) == []


def test_data_cadastrada_a_mao_tambem_e_pulada_na_agenda(client, app, monkeypatch):
    """De nada adianta cadastrar se a geração de sessões ignorar."""
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    # 26/10/2026 é uma segunda-feira.
    emenda = date(2026, 10, 26)
    assert emenda.weekday() == 0

    with app.app_context():
        fisio = db.session.scalar(db.select(User).filter_by(email="fisio@teste.com"))
        paciente = Patient(nome="Joana Ribeiro", fisioterapeuta_id=fisio.id, ativo=True)
        db.session.add(paciente)
        db.session.commit()
        ciclo = TreatmentCycle(
            paciente_id=paciente.id,
            fisioterapeuta_id=fisio.id,
            regiao="coluna",
            modalidade="INDIVIDUAL",
            data_avaliacao=HOJE,
            total_sessoes=3,
            status="ATIVO",
        )
        db.session.add(ciclo)
        db.session.commit()
        id_ciclo = ciclo.id

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    cadastrar(client, emenda.isoformat(), "Dia do servidor público (emenda)")

    client.post(
        f"/ciclos/{id_ciclo}/sessoes",
        data={
            "inicio": "2026-10-19",
            "dias": "0",
            "hora": "09:00",
            "quantidade": "3",
        },
        follow_redirects=True,
    )

    with app.app_context():
        datas = [
            a.data
            for a in Appointment.query.filter_by(ciclo_id=id_ciclo, tipo="SESSAO").all()
        ]
    assert datas, "nenhuma sessão foi gerada"
    assert emenda not in datas, "a sessão caiu na emenda"
