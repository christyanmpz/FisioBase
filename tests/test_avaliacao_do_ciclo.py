"""O ciclo de tratamento aponta para a avaliação que o justifica.

Pedido da clínica: guardar só uma data digitada à mão não diz de qual
avaliação o tratamento saiu. O ciclo passou a referenciar o atendimento de
avaliação, e a data vem dele.

O que estes testes protegem:

* abrir o ciclo exige escolher a avaliação, quando há alguma comparecida;
* a data do ciclo vem da avaliação escolhida, não do campo digitado;
* uma mesma avaliação pode justificar mais de um ciclo — decisão da
  clínica, para quando o fisioterapeuta encontra duas queixas na mesma
  consulta;
* a avaliação tem que ser do próprio paciente: um POST montado à mão não
  liga o tratamento de um paciente à avaliação de outro;
* o ciclo de grupo e os abertos antes desta mudança seguem sem vínculo, e
  a edição deles continua funcionando;
* o vínculo aparece onde se procura por ele: lista de ciclos, ficha do
  paciente e prontuário impresso.
"""

from datetime import date, time

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


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def criar_paciente(app, nome, id_fisio):
    with app.app_context():
        paciente = Patient(nome=nome, fisioterapeuta_id=id_fisio, ativo=True)
        db.session.add(paciente)
        db.session.commit()
        return paciente.id


def criar_avaliacao(
    app, id_paciente, id_fisio, dia, hora=time(13, 30), status="REALIZADO"
):
    with app.app_context():
        avaliacao = Appointment(
            tipo="AVALIACAO",
            paciente_id=id_paciente,
            fisioterapeuta_id=id_fisio,
            data=dia,
            hora=hora,
            duracao_min=30,
            status=status,
        )
        db.session.add(avaliacao)
        db.session.commit()
        return avaliacao.id


def postar_ciclo(client, id_paciente, **campos):
    dados = {
        "regiao": "JOELHO",
        "modalidade": "INDIVIDUAL",
        "total_sessoes": "10",
        "data_avaliacao": "2026-09-01",
    }
    dados.update(campos)
    return client.post(
        f"/pacientes/{id_paciente}/ciclos/novo", data=dados, follow_redirects=True
    )


def ciclos(app, id_paciente):
    with app.app_context():
        return (
            TreatmentCycle.query.filter_by(paciente_id=id_paciente)
            .order_by(TreatmentCycle.id)
            .all()
        )


def ciclo_direto(app, id_paciente, id_fisio, **campos):
    """Um ciclo gravado sem passar pelo formulário, como os antigos."""
    with app.app_context():
        dados = {
            "paciente_id": id_paciente,
            "fisioterapeuta_id": id_fisio,
            "regiao": "OMBRO",
            "modalidade": "INDIVIDUAL",
            "data_avaliacao": date(2025, 3, 10),
            "total_sessoes": 10,
            "status": "ATIVO",
        }
        dados.update(campos)
        ciclo = TreatmentCycle(**dados)
        db.session.add(ciclo)
        db.session.commit()
        return ciclo.id


# --------------------------------------------------------------------
# Abertura do ciclo
# --------------------------------------------------------------------


def test_formulario_oferece_as_avaliacoes_comparecidas(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 1), time(8, 0))
    criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 20), time(15, 30))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    html = client.get(f"/pacientes/{id_paciente}/ciclos/novo").get_data(as_text=True)

    assert 'name="avaliacao_id"' in html
    assert "01/09/2026" in html
    assert "20/09/2026" in html
    assert "15:30" in html, "a hora distingue duas avaliações no mesmo dia"


def test_avaliacao_apenas_agendada_nao_entra_na_lista(client, app, monkeypatch):
    """Agendada não é comparecida: não justifica tratamento nenhum."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 1), time(8, 0))
    futura = criar_avaliacao(
        app, id_paciente, id_fisio, date(2026, 10, 20), time(9, 0), status="AGENDADO"
    )

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    html = client.get(f"/pacientes/{id_paciente}/ciclos/novo").get_data(as_text=True)

    assert f'value="{futura}"' not in html
    assert "20/10/2026" not in html


def test_abrir_ciclo_grava_o_vinculo_e_a_data_da_avaliacao(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    id_avaliacao = criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 18))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    postar_ciclo(client, id_paciente, avaliacao_id=id_avaliacao)

    gravados = ciclos(app, id_paciente)
    assert len(gravados) == 1
    assert gravados[0].avaliacao_id == id_avaliacao
    assert gravados[0].data_avaliacao == date(2026, 9, 18)


def test_a_avaliacao_manda_na_data_mesmo_se_o_campo_divergir(client, app, monkeypatch):
    """O campo de data é ignorado quando há avaliação: duas fontes para a
    mesma informação acabariam divergindo no prontuário."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    id_avaliacao = criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 18))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    postar_ciclo(
        client,
        id_paciente,
        avaliacao_id=id_avaliacao,
        data_avaliacao="2020-01-01",
    )

    assert ciclos(app, id_paciente)[0].data_avaliacao == date(2026, 9, 18)


def test_sem_escolher_a_avaliacao_o_ciclo_nao_abre(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 18))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = postar_ciclo(client, id_paciente, avaliacao_id="")

    assert "Selecione a avaliação" in resposta.get_data(as_text=True)
    assert ciclos(app, id_paciente) == []


def test_uma_avaliacao_pode_justificar_dois_ciclos(client, app, monkeypatch):
    """Decisão da clínica: o paciente é avaliado uma vez e o fisioterapeuta
    encontra duas queixas. Os dois tratamentos saem da mesma avaliação."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    id_avaliacao = criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 18))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    postar_ciclo(client, id_paciente, avaliacao_id=id_avaliacao, regiao="JOELHO")
    postar_ciclo(client, id_paciente, avaliacao_id=id_avaliacao, regiao="COLUNA")

    gravados = ciclos(app, id_paciente)
    assert len(gravados) == 2
    assert {c.regiao for c in gravados} == {"JOELHO", "COLUNA"}
    assert all(c.avaliacao_id == id_avaliacao for c in gravados)


# --------------------------------------------------------------------
# Um POST montado à mão não liga prontuários diferentes
# --------------------------------------------------------------------


def test_avaliacao_de_outro_paciente_e_recusada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 18))

    id_outro = criar_paciente(app, "Bruno Teles", id_fisio)
    alheia = criar_avaliacao(app, id_outro, id_fisio, date(2026, 9, 19))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = postar_ciclo(client, id_paciente, avaliacao_id=alheia)

    assert "avaliação válida deste paciente" in resposta.get_data(as_text=True)
    assert ciclos(app, id_paciente) == []


def test_sessao_comum_nao_serve_de_avaliacao(client, app, monkeypatch):
    """Só atendimento do tipo AVALIACAO justifica um ciclo."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 18))

    with app.app_context():
        sessao = Appointment(
            tipo="SESSAO",
            paciente_id=id_paciente,
            fisioterapeuta_id=id_fisio,
            data=date(2026, 9, 25),
            hora=time(10, 0),
            status="REALIZADO",
        )
        db.session.add(sessao)
        db.session.commit()
        id_sessao = sessao.id

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = postar_ciclo(client, id_paciente, avaliacao_id=id_sessao)

    assert "avaliação válida deste paciente" in resposta.get_data(as_text=True)
    assert ciclos(app, id_paciente) == []


def test_avaliacao_inexistente_nao_derruba_a_pagina(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 18))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = postar_ciclo(client, id_paciente, avaliacao_id="90210")

    assert resposta.status_code == 400, "devolve o formulário com erro, não um 500"
    assert "avaliação válida deste paciente" in resposta.get_data(as_text=True)
    assert ciclos(app, id_paciente) == []


def test_avaliacao_que_nao_e_numero_nao_derruba_a_pagina(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 18))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = postar_ciclo(client, id_paciente, avaliacao_id="x; drop table")

    assert resposta.status_code == 400, "devolve o formulário com erro, não um 500"
    assert "avaliação válida" in resposta.get_data(as_text=True)
    assert ciclos(app, id_paciente) == []


# --------------------------------------------------------------------
# Edição: corrigir o vínculo dos ciclos que já existem
# --------------------------------------------------------------------


def test_editar_ciclo_antigo_amarra_a_avaliacao(client, app, monkeypatch):
    """Os ciclos abertos antes desta mudança ficaram sem vínculo. O Editar é
    por onde se corrige um por um."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    id_avaliacao = criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 18))
    id_ciclo = ciclo_direto(app, id_paciente, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    client.post(
        f"/ciclos/{id_ciclo}/editar",
        data={
            "regiao": "OMBRO",
            "modalidade": "INDIVIDUAL",
            "total_sessoes": "10",
            "avaliacao_id": id_avaliacao,
            "data_avaliacao": "2025-03-10",
        },
        follow_redirects=True,
    )

    with app.app_context():
        ciclo = db.session.get(TreatmentCycle, id_ciclo)
        assert ciclo.avaliacao_id == id_avaliacao
        assert ciclo.data_avaliacao == date(2026, 9, 18)


def test_editar_ciclo_sem_avaliacao_continua_aceitando_a_data(client, app, monkeypatch):
    """O ciclo de grupo não tem avaliação própria. Se a edição exigisse o
    vínculo, não seria possível corrigir mais nada nele."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    id_ciclo = ciclo_direto(app, id_paciente, id_fisio, modalidade="GRUPO")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    client.post(
        f"/ciclos/{id_ciclo}/editar",
        data={
            "regiao": "COLUNA",
            "modalidade": "GRUPO",
            "total_sessoes": "12",
            "avaliacao_id": "",
            "data_avaliacao": "2025-04-07",
        },
        follow_redirects=True,
    )

    with app.app_context():
        ciclo = db.session.get(TreatmentCycle, id_ciclo)
        assert ciclo.avaliacao_id is None
        assert ciclo.regiao == "COLUNA"
        assert ciclo.total_sessoes == 12
        assert ciclo.data_avaliacao == date(2025, 4, 7)


def test_editar_ciclo_pode_desfazer_o_vinculo(client, app, monkeypatch):
    """Vínculo errado em prontuário é pior que vínculo vazio: tem que dar
    para desfazer."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    id_avaliacao = criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 18))
    id_ciclo = ciclo_direto(app, id_paciente, id_fisio, avaliacao_id=id_avaliacao)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    client.post(
        f"/ciclos/{id_ciclo}/editar",
        data={
            "regiao": "OMBRO",
            "modalidade": "INDIVIDUAL",
            "total_sessoes": "10",
            "avaliacao_id": "",
            "data_avaliacao": "2025-03-10",
        },
        follow_redirects=True,
    )

    with app.app_context():
        assert db.session.get(TreatmentCycle, id_ciclo).avaliacao_id is None


def test_formulario_de_edicao_marca_a_avaliacao_vinculada(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 1), time(8, 0))
    escolhida = criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 20))
    id_ciclo = ciclo_direto(app, id_paciente, id_fisio, avaliacao_id=escolhida)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    html = client.get(f"/ciclos/{id_ciclo}/editar").get_data(as_text=True)

    assert f'value="{escolhida}"' in html
    marca = html.find(f'value="{escolhida}"')
    assert "selected" in html[marca : marca + 80], "a vinculada deve vir marcada"


def test_editar_nao_aceita_avaliacao_de_outro_paciente(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    id_ciclo = ciclo_direto(app, id_paciente, id_fisio)

    id_outro = criar_paciente(app, "Bruno Teles", id_fisio)
    alheia = criar_avaliacao(app, id_outro, id_fisio, date(2026, 9, 19))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(
        f"/ciclos/{id_ciclo}/editar",
        data={
            "regiao": "OMBRO",
            "modalidade": "INDIVIDUAL",
            "total_sessoes": "10",
            "avaliacao_id": alheia,
            "data_avaliacao": "2025-03-10",
        },
    )

    assert resposta.status_code == 400
    with app.app_context():
        assert db.session.get(TreatmentCycle, id_ciclo).avaliacao_id is None


# --------------------------------------------------------------------
# Onde o vínculo aparece
# --------------------------------------------------------------------


def test_a_lista_de_ciclos_mostra_a_avaliacao_de_referencia(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    id_avaliacao = criar_avaliacao(
        app, id_paciente, id_fisio, date(2026, 9, 18), time(16, 15)
    )
    ciclo_direto(app, id_paciente, id_fisio, avaliacao_id=id_avaliacao)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    html = client.get(f"/pacientes/{id_paciente}/ciclos").get_data(as_text=True)

    assert "vinculada · 16:15" in html
    assert (
        "Avaliação de 18/09/2026 às 16:15, por Rafael Santos" in html
    ), "o nome de quem avaliou fica no title, que a coluna estreita não comporta"
    assert "avaliação feita por Rafael Santos" in html, "falta o texto para leitor"


def test_ciclo_sem_vinculo_diz_que_nao_tem(client, app, monkeypatch):
    """Silêncio pareceria vínculo; o ciclo antigo tem que se declarar."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    ciclo_direto(app, id_paciente, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    html = client.get(f"/pacientes/{id_paciente}/ciclos").get_data(as_text=True)

    assert "sem vínculo" in html


def test_a_ficha_do_paciente_mostra_o_vinculo(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    id_avaliacao = criar_avaliacao(
        app, id_paciente, id_fisio, date(2026, 9, 18), time(16, 15)
    )
    ciclo_direto(app, id_paciente, id_fisio, avaliacao_id=id_avaliacao)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    html = client.get(f"/pacientes/{id_paciente}").get_data(as_text=True)

    assert "vinculo-avaliacao" in html
    assert "16:15" in html


def test_o_prontuario_impresso_escreve_a_referencia_por_extenso(
    client, app, monkeypatch
):
    """No papel não há link para seguir: a referência vai escrita."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    id_avaliacao = criar_avaliacao(
        app, id_paciente, id_fisio, date(2026, 9, 18), time(16, 15)
    )
    ciclo_direto(app, id_paciente, id_fisio, avaliacao_id=id_avaliacao)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    html = client.get(f"/pacientes/{id_paciente}/prontuario").get_data(as_text=True)

    assert "Avaliação de referência" in html
    assert "18/09/2026" in html
    assert "16:15" in html
    assert f"nº {id_avaliacao}" in html


# --------------------------------------------------------------------
# Escopo: cada um vê as avaliações que pode ver
# --------------------------------------------------------------------


def test_administracao_tambem_escolhe_a_avaliacao(client, app, monkeypatch):
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    id_avaliacao = criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 18))

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    postar_ciclo(client, id_paciente, avaliacao_id=id_avaliacao)

    assert ciclos(app, id_paciente)[0].avaliacao_id == id_avaliacao


def test_avaliacao_feita_por_outro_profissional_pode_ser_vinculada(
    client, app, monkeypatch
):
    """A triagem é de quem está na escala; o tratamento, de quem acompanha o
    paciente. Os dois podem ser profissionais diferentes."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)

    with app.app_context():
        db.session.add(
            criar_usuario(
                "Iara Bastos", "outra@teste.com", SENHA_FISIO, PHYSIOTHERAPIST_PROFILE
            )
        )
        db.session.commit()
        id_outra = db.session.scalar(
            db.select(User.id).where(User.email == "outra@teste.com")
        )

    id_avaliacao = criar_avaliacao(app, id_paciente, id_outra, date(2026, 9, 18))

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    postar_ciclo(client, id_paciente, avaliacao_id=id_avaliacao)

    gravados = ciclos(app, id_paciente)
    assert len(gravados) == 1
    assert gravados[0].avaliacao_id == id_avaliacao


def test_apagar_a_avaliacao_nao_leva_o_ciclo(client, app, monkeypatch):
    """ON DELETE SET NULL no banco. Aqui conferimos o lado do código: o
    tratamento sobrevive ao vínculo."""
    fixar_hoje(monkeypatch)
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_paciente = criar_paciente(app, "Ana Lima", id_fisio)
    id_avaliacao = criar_avaliacao(app, id_paciente, id_fisio, date(2026, 9, 18))
    id_ciclo = ciclo_direto(app, id_paciente, id_fisio, avaliacao_id=id_avaliacao)

    with app.app_context():
        ciclo = db.session.get(TreatmentCycle, id_ciclo)
        ciclo.avaliacao_id = None
        db.session.delete(db.session.get(Appointment, id_avaliacao))
        db.session.commit()

        assert db.session.get(TreatmentCycle, id_ciclo) is not None

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    html = client.get(f"/pacientes/{id_paciente}/ciclos").get_data(as_text=True)
    assert "sem vínculo" in html
