"""Composição do grupo: entrada e saída de pacientes.

A saída nunca apaga a linha, para preservar o histórico de presença.
"""

from datetime import date, time

from conftest import SENHA_ADMIN, SENHA_FISIO, criar_usuario, fazer_login
from models import (
    PHYSIOTHERAPIST_PROFILE,
    Group,
    GroupPatient,
    Patient,
    TreatmentCycle,
    User,
    db,
)

SENHA_NOVA = "Nova@1234"
TERCA = 1


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def criar_grupo(app, fisioterapeuta_id, **campos):
    dados = {
        "nome": "Grupo Ombro manhã",
        "regiao": "OMBRO",
        "fisioterapeuta_id": fisioterapeuta_id,
        "dia_semana": TERCA,
        "hora": time(8, 0),
        "capacidade_max": 14,
        "ativo": True,
    }
    dados.update(campos)
    with app.app_context():
        grupo = Group(**dados)
        db.session.add(grupo)
        db.session.commit()
        return grupo.id


def criar_paciente(app, fisioterapeuta_id, nome="Ana Prado", ativo=True):
    with app.app_context():
        paciente = Patient(nome=nome, fisioterapeuta_id=fisioterapeuta_id, ativo=ativo)
        db.session.add(paciente)
        db.session.commit()
        return paciente.id


def criar_ciclo(app, paciente_id, fisioterapeuta_id, status="ATIVO"):
    with app.app_context():
        ciclo = TreatmentCycle(
            paciente_id=paciente_id,
            fisioterapeuta_id=fisioterapeuta_id,
            regiao="OMBRO",
            modalidade="GRUPO",
            data_avaliacao=date(2026, 9, 1),
            total_sessoes=6,
            status=status,
        )
        db.session.add(ciclo)
        db.session.commit()
        return ciclo.id


def adicionar(client, grupo_id, paciente_id, ciclo_id=""):
    return client.post(
        f"/grupos/{grupo_id}/pacientes",
        data={"paciente_id": str(paciente_id), "ciclo_id": str(ciclo_id)},
    )


def participacoes(app, grupo_id):
    with app.app_context():
        return (
            GroupPatient.query.filter_by(grupo_id=grupo_id)
            .order_by(GroupPatient.id)
            .all()
        )


def ativas(app, grupo_id):
    return [p for p in participacoes(app, grupo_id) if p.data_saida is None]


# ----------------------------------------------------------------------
# Entrada no grupo
# ----------------------------------------------------------------------


def test_condutor_adiciona_paciente_ao_grupo(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    assert adicionar(client, id_grupo, id_paciente).status_code == 302

    lista = ativas(app, id_grupo)
    assert len(lista) == 1
    assert lista[0].paciente_id == id_paciente
    assert lista[0].ciclo_id is None
    assert lista[0].data_saida is None


def test_adicionar_vinculando_um_ciclo_ativo(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)
    id_ciclo = criar_ciclo(app, id_paciente, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    adicionar(client, id_grupo, id_paciente, id_ciclo)

    assert ativas(app, id_grupo)[0].ciclo_id == id_ciclo


def test_ciclo_encerrado_e_recusado(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)
    id_ciclo = criar_ciclo(app, id_paciente, id_fisio, status="ALTA")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    adicionar(client, id_grupo, id_paciente, id_ciclo)

    assert ativas(app, id_grupo) == []


def test_ciclo_de_outro_paciente_e_recusado(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)
    id_outro = criar_paciente(app, id_fisio, nome="Outro Paciente")
    id_ciclo = criar_ciclo(app, id_outro, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    adicionar(client, id_grupo, id_paciente, id_ciclo)

    assert ativas(app, id_grupo) == []


def test_mesmo_paciente_duas_vezes_e_recusado(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    adicionar(client, id_grupo, id_paciente)
    adicionar(client, id_grupo, id_paciente)

    assert len(ativas(app, id_grupo)) == 1


def test_paciente_inativo_e_recusado(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio, ativo=False)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    adicionar(client, id_grupo, id_paciente)

    assert ativas(app, id_grupo) == []


def test_grupo_lotado_recusa_entrada(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio, capacidade_max=2)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    for numero in range(3):
        adicionar(
            client, id_grupo, criar_paciente(app, id_fisio, nome=f"Paciente {numero}")
        )

    assert len(ativas(app, id_grupo)) == 2


def test_grupo_desativado_nao_recebe_paciente(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio, ativo=False)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    adicionar(client, id_grupo, id_paciente)

    assert ativas(app, id_grupo) == []


# ----------------------------------------------------------------------
# Quem pode compor
# ----------------------------------------------------------------------


def test_fisioterapeuta_nao_adiciona_paciente_de_outro(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)

    with app.app_context():
        db.session.add(
            criar_usuario(
                "Outra Fisio", "outra@teste.com", SENHA_NOVA, PHYSIOTHERAPIST_PROFILE
            )
        )
        db.session.commit()
    id_outra = id_do_usuario(app, "outra@teste.com")
    id_paciente = criar_paciente(app, id_outra, nome="Paciente da outra")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    assert adicionar(client, id_grupo, id_paciente).status_code == 403
    assert ativas(app, id_grupo) == []


def test_admin_adiciona_qualquer_paciente(client, app):
    id_admin = id_do_usuario(app, "admin@teste.com")
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_admin)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    adicionar(client, id_grupo, id_paciente)

    assert len(ativas(app, id_grupo)) == 1


def test_formulario_lista_so_pacientes_acessiveis(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    criar_paciente(app, id_fisio, nome="Paciente do fisio")

    with app.app_context():
        db.session.add(
            criar_usuario(
                "Outra Fisio", "outra@teste.com", SENHA_NOVA, PHYSIOTHERAPIST_PROFILE
            )
        )
        db.session.commit()
    criar_paciente(app, id_do_usuario(app, "outra@teste.com"), nome="Paciente da outra")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    corpo = client.get(f"/grupos/{id_grupo}/pacientes").get_data(as_text=True)

    assert "Paciente do fisio" in corpo
    assert "Paciente da outra" not in corpo


def test_quem_ja_esta_no_grupo_sai_da_lista_de_disponiveis(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio, nome="Ana Prado")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    adicionar(client, id_grupo, id_paciente)
    corpo = client.get(f"/grupos/{id_grupo}/pacientes").get_data(as_text=True)

    assert corpo.count(f'<option value="{id_paciente}">') == 0
    assert "Ana Prado" in corpo


def test_outro_fisioterapeuta_nao_abre_a_composicao(client, app):
    id_admin = id_do_usuario(app, "admin@teste.com")
    id_grupo = criar_grupo(app, id_admin)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    assert client.get(f"/grupos/{id_grupo}/pacientes").status_code == 403


def test_composicao_exige_login(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)

    resposta = client.get(f"/grupos/{id_grupo}/pacientes")

    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


# ----------------------------------------------------------------------
# Saída do grupo
# ----------------------------------------------------------------------


def test_saida_preenche_a_data_sem_apagar_a_linha(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    adicionar(client, id_grupo, id_paciente)
    id_participacao = ativas(app, id_grupo)[0].id

    client.post(f"/grupos/{id_grupo}/pacientes/{id_participacao}/saida")

    todas = participacoes(app, id_grupo)
    assert len(todas) == 1
    assert todas[0].data_saida is not None
    assert ativas(app, id_grupo) == []


def test_saida_libera_vaga_no_grupo_lotado(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio, capacidade_max=1)
    id_primeiro = criar_paciente(app, id_fisio, nome="Primeiro")
    id_segundo = criar_paciente(app, id_fisio, nome="Segundo")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    adicionar(client, id_grupo, id_primeiro)
    adicionar(client, id_grupo, id_segundo)
    assert len(ativas(app, id_grupo)) == 1

    client.post(f"/grupos/{id_grupo}/pacientes/{ativas(app, id_grupo)[0].id}/saida")
    adicionar(client, id_grupo, id_segundo)

    assert len(ativas(app, id_grupo)) == 1
    assert len(participacoes(app, id_grupo)) == 2


def test_paciente_que_saiu_pode_voltar_em_linha_nova(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    adicionar(client, id_grupo, id_paciente)
    client.post(f"/grupos/{id_grupo}/pacientes/{ativas(app, id_grupo)[0].id}/saida")
    adicionar(client, id_grupo, id_paciente)

    todas = participacoes(app, id_grupo)
    assert len(todas) == 2
    assert todas[0].data_saida is not None
    assert todas[1].data_saida is None


def test_registrar_saida_duas_vezes_nao_muda_a_data(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    adicionar(client, id_grupo, id_paciente)
    id_participacao = ativas(app, id_grupo)[0].id

    client.post(f"/grupos/{id_grupo}/pacientes/{id_participacao}/saida")
    primeira = participacoes(app, id_grupo)[0].data_saida
    client.post(f"/grupos/{id_grupo}/pacientes/{id_participacao}/saida")

    assert participacoes(app, id_grupo)[0].data_saida == primeira


def test_outro_fisioterapeuta_nao_registra_saida(client, app):
    id_admin = id_do_usuario(app, "admin@teste.com")
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_admin)
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    adicionar(client, id_grupo, id_paciente)
    id_participacao = ativas(app, id_grupo)[0].id
    client.post("/logout")

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    resposta = client.post(f"/grupos/{id_grupo}/pacientes/{id_participacao}/saida")

    assert resposta.status_code == 403
    assert len(ativas(app, id_grupo)) == 1


def test_participacao_de_outro_grupo_da_404(client, app):
    id_fisio = id_do_usuario(app, "fisio@teste.com")
    id_grupo = criar_grupo(app, id_fisio)
    id_outro = criar_grupo(app, id_fisio, nome="Outro grupo", hora=time(9, 0))
    id_paciente = criar_paciente(app, id_fisio)

    fazer_login(client, "fisio@teste.com", SENHA_FISIO)
    adicionar(client, id_grupo, id_paciente)
    id_participacao = ativas(app, id_grupo)[0].id

    resposta = client.post(f"/grupos/{id_outro}/pacientes/{id_participacao}/saida")

    assert resposta.status_code == 404
    assert len(ativas(app, id_grupo)) == 1
