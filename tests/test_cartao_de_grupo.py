"""O cartão de grupo tem que se diferenciar do individual.

Os dois saíam com o mesmo título, e o cartão de grupo não dizia de qual
turma eram aquelas datas. Pior: prometia avisar a falta "com antecedência",
o que no individual dá reposição — no grupo, não dá.
"""

from datetime import date, time

import app as modulo_app
from conftest import SENHA_FISIO, fazer_login
from models import Group, GroupPatient, Patient, TreatmentCycle, User, db

HOJE = date(2026, 9, 22)
TERCA = 1


def _cenario(app, modalidade):
    """Cria um paciente com um ciclo da modalidade pedida."""
    with app.app_context():
        fisio = db.session.scalar(db.select(User).filter_by(email="fisio@teste.com"))
        paciente = Patient(nome="Joana Ribeiro", fisioterapeuta_id=fisio.id, ativo=True)
        db.session.add(paciente)
        db.session.commit()

        ciclo = TreatmentCycle(
            paciente_id=paciente.id,
            fisioterapeuta_id=fisio.id,
            regiao="coluna",
            modalidade=modalidade,
            data_avaliacao=HOJE,
            total_sessoes=12 if modalidade == "GRUPO" else 10,
            status="ATIVO",
        )
        db.session.add(ciclo)
        db.session.commit()

        if modalidade == "GRUPO":
            grupo = Group(
                nome="Grupo Coluna — turma da tarde",
                regiao="COLUNA",
                fisioterapeuta_id=fisio.id,
                dia_semana=TERCA,
                hora=time(14, 30),
                capacidade_max=14,
                total_semanas=6,
                ativo=True,
            )
            db.session.add(grupo)
            db.session.commit()
            db.session.add(
                GroupPatient(
                    grupo_id=grupo.id,
                    paciente_id=paciente.id,
                    ciclo_id=ciclo.id,
                    data_entrada=HOJE,
                )
            )
            db.session.commit()
        return ciclo.id


def test_cartao_de_grupo_diz_que_e_de_grupo(client, app, monkeypatch):
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    id_ciclo = _cenario(app, "GRUPO")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = client.get(f"/ciclos/{id_ciclo}/cartao").get_data(as_text=True)

    assert "Cartão de atendimento em grupo" in html


def test_cartao_de_grupo_mostra_a_turma_e_o_encontro(client, app, monkeypatch):
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    id_ciclo = _cenario(app, "GRUPO")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = client.get(f"/ciclos/{id_ciclo}/cartao").get_data(as_text=True)

    assert "Grupo Coluna — turma da tarde" in html
    assert "14:30" in html
    assert "Encontro semanal" in html


def test_cartao_de_grupo_nao_promete_reposicao(client, app, monkeypatch):
    """No grupo a data é da turma inteira: não existe reposição individual."""
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    id_ciclo = _cenario(app, "GRUPO")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = client.get(f"/ciclos/{id_ciclo}/cartao").get_data(as_text=True)

    assert "não há sessão de reposição individual" in html


def test_cartao_individual_segue_igual(client, app, monkeypatch):
    """A mudança não pode encostar no cartão do atendimento individual."""
    monkeypatch.setattr(modulo_app, "hoje", lambda: HOJE)
    id_ciclo = _cenario(app, "INDIVIDUAL")
    fazer_login(client, "fisio@teste.com", SENHA_FISIO)

    html = client.get(f"/ciclos/{id_ciclo}/cartao").get_data(as_text=True)

    assert "Cartão de atendimento" in html
    assert "em grupo" not in html
    assert "Região tratada" in html
    assert "Encontro semanal" not in html
    assert "Em caso de falta, avise a recepção com antecedência." in html
