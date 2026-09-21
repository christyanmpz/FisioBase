"""Nº do cartão cidadão no cadastro do paciente.

Identificação oficial do município. Nem todo paciente tem, então é
opcional — mas quando vem preenchido precisa ser um número de 10 a 15
dígitos, e serve para achar o paciente na busca.
"""

from conftest import SENHA_ADMIN, fazer_login
from models import Patient, User, db


def id_do_usuario(app, email):
    with app.app_context():
        return db.session.scalar(db.select(User).where(User.email == email)).id


def cadastrar(client, **campos):
    dados = {"nome": "Josefa Andrade"}
    dados.update(campos)
    return client.post("/pacientes/novo", data=dados, follow_redirects=True)


def cartao_do_paciente(app, nome="Josefa Andrade"):
    with app.app_context():
        paciente = db.session.scalar(db.select(Patient).where(Patient.nome == nome))
        return paciente.cartao_cidadao if paciente else None


def test_salva_o_cartao_com_dez_digitos(client, app):
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    cadastrar(client, cartao_cidadao="1234567890")

    assert cartao_do_paciente(app) == "1234567890"


def test_salva_o_cartao_com_quinze_digitos(client, app):
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    cadastrar(client, cartao_cidadao="123456789012345")

    assert cartao_do_paciente(app) == "123456789012345"


def test_limpa_pontuacao_digitada(client, app):
    """A recepção copia do cartão com espaço e ponto; guarda só os dígitos."""
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    cadastrar(client, cartao_cidadao="123.456.789-012")

    assert cartao_do_paciente(app) == "123456789012"


def test_recusa_cartao_curto_demais(client, app):
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    resposta = cadastrar(client, cartao_cidadao="123456789")

    assert "10 a 15 dígitos" in resposta.get_data(as_text=True)
    assert cartao_do_paciente(app) is None


def test_recusa_cartao_longo_demais(client, app):
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    resposta = cadastrar(client, cartao_cidadao="1234567890123456")

    assert "10 a 15 dígitos" in resposta.get_data(as_text=True)
    assert cartao_do_paciente(app) is None


def test_cartao_em_branco_e_aceito(client, app):
    """Paciente de fora do município não tem cartão; não pode travar."""
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    cadastrar(client, cartao_cidadao="")

    with app.app_context():
        paciente = db.session.scalar(
            db.select(Patient).where(Patient.nome == "Josefa Andrade")
        )
        assert paciente is not None
        assert paciente.cartao_cidadao is None


def test_busca_encontra_pelo_cartao(client, app):
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    cadastrar(client, cartao_cidadao="9876543210")
    cadastrar(client, nome="Outro Paciente", cartao_cidadao="1112223330")

    pagina = client.get("/pacientes?q=9876543210").get_data(as_text=True)

    assert "Josefa Andrade" in pagina
    assert "Outro Paciente" not in pagina


def test_cartao_aparece_na_ficha(client, app):
    fazer_login(client, "admin@teste.com", SENHA_ADMIN)
    cadastrar(client, cartao_cidadao="5556667770")

    with app.app_context():
        id_paciente = db.session.scalar(
            db.select(Patient).where(Patient.nome == "Josefa Andrade")
        ).id

    pagina = client.get(f"/pacientes/{id_paciente}").get_data(as_text=True)

    assert "5556667770" in pagina
    assert "Cartão cidadão" in pagina
