"""Ficha em branco para o fisioterapeuta preencher à mão.

A clínica pediu que o registro clínico pudesse ser feito no papel ou na
tela, a critério do profissional. O sistema entra com a identificação e
deixa o resto pautado, seguindo a Resolução COFFITO nº 414/2012.

O que estes testes protegem:

* a ficha da avaliação e a da sessão são diferentes — uma cobre história
  clínica e plano terapêutico, a outra segue o modelo SOAP;
* a identificação sai preenchida, para ninguém copiar CPF à mão;
* ao contrário da evolução digital, a ficha **não** é bloqueada por
  sessão futura, falta ou cancelamento: imprimir antes do atendimento é
  justamente o uso dela;
* o sigilo continua valendo — quem não enxerga o paciente não imprime a
  ficha dele.
"""

from datetime import date, time, timedelta

import app as modulo_app
from conftest import SENHA_ADMIN, SENHA_FISIO, criar_usuario, fazer_login
from models import (
    PHYSIOTHERAPIST_PROFILE,
    Appointment,
    Patient,
    TreatmentCycle,
    User,
    db,
)

HOJE = date(2026, 10, 1)


def fixar_hoje(monkeypatch, dia=HOJE):
    monkeypatch.setattr(modulo_app, "hoje", lambda: dia)


def montar(app, tipo="SESSAO", status="REALIZADO", dia=None, com_ciclo=True):
    """Um atendimento pronto para imprimir, e devolve os ids que importam.

    O CPF é único no banco, e alguns testes montam mais de um paciente;
    por isso o documento do primeiro é o que aparece na ficha e os
    seguintes recebem um número qualquer, que nenhum teste confere.
    """
    with app.app_context():
        fisio = db.session.scalar(db.select(User).filter_by(email="fisio@teste.com"))
        quantos = db.session.scalar(db.select(db.func.count(Patient.id))) or 0
        paciente = Patient(
            nome="Adelina Peixoto",
            fisioterapeuta_id=fisio.id,
            ativo=True,
            cpf="529.982.247-25" if quantos == 0 else f"000.000.000-{quantos:02d}",
            cartao_cidadao="708203049810006" if quantos == 0 else None,
            data_nascimento=date(1958, 4, 17),
        )
        db.session.add(paciente)
        db.session.flush()

        ciclo_id = None
        numero = None
        if com_ciclo:
            ciclo = TreatmentCycle(
                paciente_id=paciente.id,
                fisioterapeuta_id=fisio.id,
                regiao="OMBRO",
                modalidade="INDIVIDUAL",
                data_avaliacao=date(2026, 9, 10),
                total_sessoes=10,
                status="ATIVO",
                cid="M75.1",
            )
            db.session.add(ciclo)
            db.session.flush()
            ciclo_id = ciclo.id
            numero = 3

        agendamento = Appointment(
            tipo=tipo,
            paciente_id=paciente.id,
            ciclo_id=ciclo_id,
            numero_sessao=numero,
            fisioterapeuta_id=fisio.id,
            data=dia or date(2026, 9, 24),
            hora=time(14, 30),
            status=status,
        )
        db.session.add(agendamento)
        db.session.commit()
        return {
            "agendamento": agendamento.id,
            "paciente": paciente.id,
            "fisio": fisio.id,
        }


def imprimir(client, id_agendamento):
    return client.get(f"/agendamentos/{id_agendamento}/ficha")


# --------------------------------------------------------------------
# Conteúdo: a ficha certa para cada tipo de atendimento
# --------------------------------------------------------------------


def test_ficha_da_sessao_segue_o_modelo_soap(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    ids = montar(app, tipo="SESSAO")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = imprimir(client, ids["agendamento"]).get_data(as_text=True)

    assert "Ficha de evolução — sessão" in html
    for bloco in ("S · Subjetivo", "O · Objetivo", "A · Avaliação", "P · Plano"):
        assert bloco in html, f"a ficha da sessão não tem o bloco {bloco}"
    assert "Intercorrências" in html


def test_ficha_da_avaliacao_cobre_o_que_o_coffito_exige(client, app, monkeypatch):
    """Resolução COFFITO nº 414/2012, Art. 1º § 1º, itens II a VI."""
    fixar_hoje(monkeypatch)
    ids = montar(app, tipo="AVALIACAO")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = imprimir(client, ids["agendamento"]).get_data(as_text=True)

    assert "Ficha de avaliação fisioterapêutica" in html
    for bloco in (
        "Queixa principal",
        "História clínica",
        "Exame físico-funcional",
        "Exames complementares",
        "Diagnóstico e prognóstico fisioterapêuticos",
        "Plano terapêutico",
    ):
        assert bloco in html, f"a ficha de avaliação não tem o bloco {bloco}"


def test_cada_tipo_mostra_so_a_sua_ficha(client, app, monkeypatch):
    """Sem isto, uma ficha com os dois conteúdos passaria nos testes acima."""
    fixar_hoje(monkeypatch)
    ids = montar(app, tipo="SESSAO")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    sessao = imprimir(client, ids["agendamento"]).get_data(as_text=True)
    assert "Plano terapêutico" not in sessao
    assert "História clínica" not in sessao

    ids = montar(app, tipo="AVALIACAO")
    avaliacao = imprimir(client, ids["agendamento"]).get_data(as_text=True)
    assert "S · Subjetivo" not in avaliacao
    assert "Intercorrências" not in avaliacao


def test_a_ficha_tem_espaco_pautado_para_escrever(client, app, monkeypatch):
    """Uma ficha sem linha é um papel em branco: não serve de prontuário."""
    fixar_hoje(monkeypatch)
    ids = montar(app, tipo="AVALIACAO")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = imprimir(client, ids["agendamento"]).get_data(as_text=True)

    assert html.count('class="ficha-pauta"') >= 6
    assert "ficha-escala" in html, "falta a régua de dor (EVA)"
    assert "Força (MRC 0–5)" in html, "falta a tabela de goniometria e força"


# --------------------------------------------------------------------
# Identificação: o sistema preenche o que já sabe
# --------------------------------------------------------------------


def test_identificacao_sai_preenchida(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    ids = montar(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = imprimir(client, ids["agendamento"]).get_data(as_text=True)

    assert "Adelina Peixoto" in html
    assert "529.982.247-25" in html
    assert "708203049810006" in html
    assert "17/04/1958" in html
    assert "Rafael Santos" in html
    assert "24/09/2026" in html
    assert "14:30" in html
    assert "Quinta" in html, "o dia da semana ajuda quem arquiva o papel"


def test_ficha_do_ciclo_diz_regiao_cid_e_numero_da_sessao(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    ids = montar(app, com_ciclo=True)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = imprimir(client, ids["agendamento"]).get_data(as_text=True)

    assert "Ombro" in html
    assert "M75.1" in html
    assert "3 de 10" in html


def test_atendimento_sem_ciclo_nao_quebra_a_ficha(client, app, monkeypatch):
    """Triagem e encaixe não têm ciclo: os campos do ciclo saem de cena."""
    fixar_hoje(monkeypatch)
    ids = montar(app, com_ciclo=False)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    resposta = imprimir(client, ids["agendamento"])
    html = resposta.get_data(as_text=True)

    assert resposta.status_code == 200
    assert "Adelina Peixoto" in html
    assert "Região tratada" not in html
    assert "CID" not in html


def test_a_folha_se_explica_sozinha_fora_do_sistema(client, app, monkeypatch):
    """Quem acha o papel na pasta tem que saber o que ele é e de quando."""
    fixar_hoje(monkeypatch)
    ids = montar(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = imprimir(client, ids["agendamento"]).get_data(as_text=True)

    inicio = html.find('class="print-rodape"')
    assert inicio > -1, "a ficha não tem rodapé de impressão"
    rodape = html[inicio : html.find("</p>", inicio)]
    assert "01/10/2026" in rodape, "o rodapé deve carimbar a data da emissão"
    assert "prontuário" in rodape, "o rodapé deve dizer o que fazer com o papel"
    assert "CREFITO" in html, "falta o espaço de assinatura e carimbo"


# --------------------------------------------------------------------
# Acesso: menos travas que a evolução digital, mesmo sigilo
# --------------------------------------------------------------------


def test_sessao_futura_imprime_a_ficha(client, app, monkeypatch):
    """A evolução digital barra sessão futura. A ficha é o contrário:
    imprime-se antes do atendimento, para levar na mão."""
    fixar_hoje(monkeypatch)
    ids = montar(app, status="AGENDADO", dia=HOJE + timedelta(days=5))
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert imprimir(client, ids["agendamento"]).status_code == 200

    bloqueada = client.get(f"/agendamentos/{ids['agendamento']}/evolucao")
    assert (
        bloqueada.status_code != 200
    ), "a evolução digital de sessão futura deveria continuar bloqueada"


def test_sessao_cancelada_ou_faltada_ainda_imprime(client, app, monkeypatch):
    """A folha pode ter sido preenchida antes de a situação mudar."""
    fixar_hoje(monkeypatch)
    for situacao in ("CANCELADO", "FALTOU", "FALTA_JUSTIFICADA"):
        ids = montar(app, status=situacao)
        fazer_login(client, "fisio@teste.com", SENHA_FISIO)
        resposta = imprimir(client, ids["agendamento"])
        assert resposta.status_code == 200, f"{situacao} deveria imprimir a ficha"


def test_a_ficha_do_paciente_oferece_a_folha_quando_nao_cabe_evolucao(
    client, app, monkeypatch
):
    """Antes aparecia só um traço na coluna Evolução da sessão futura."""
    fixar_hoje(monkeypatch)
    ids = montar(app, status="AGENDADO", dia=HOJE + timedelta(days=5))
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = client.get(f"/pacientes/{ids['paciente']}").get_data(as_text=True)

    assert f"/agendamentos/{ids['agendamento']}/ficha" in html


def test_a_tela_de_evolucao_leva_para_a_ficha(client, app, monkeypatch):
    """Foi o caminho que a clínica pediu: o botão Evolução tem que oferecer
    imprimir a folha."""
    fixar_hoje(monkeypatch)
    ids = montar(app)
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = client.get(f"/agendamentos/{ids['agendamento']}/evolucao").get_data(
        as_text=True
    )

    assert f"/agendamentos/{ids['agendamento']}/ficha" in html
    assert "preencher à mão" in html


def test_outro_fisioterapeuta_nao_imprime_a_ficha(client, app, monkeypatch):
    """O sigilo do prontuário não muda por ser papel."""
    fixar_hoje(monkeypatch)
    ids = montar(app)
    with app.app_context():
        db.session.add(
            criar_usuario(
                "Iara Bastos",
                "outra@teste.com",
                SENHA_FISIO,
                PHYSIOTHERAPIST_PROFILE,
            )
        )
        db.session.commit()

    fazer_login(client, "outra@teste.com", SENHA_FISIO)
    assert imprimir(client, ids["agendamento"]).status_code == 403


def test_administracao_imprime_a_ficha_de_qualquer_paciente(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    ids = montar(app)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    assert imprimir(client, ids["agendamento"]).status_code == 200


def test_visitante_nao_imprime_a_ficha(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    ids = montar(app)

    resposta = imprimir(client, ids["agendamento"])

    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_agendamento_inexistente_devolve_404(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    montar(app)
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)

    assert imprimir(client, 90210).status_code == 404
