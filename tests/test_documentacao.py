"""A documentação precisa continuar batendo com o sistema.

Os documentos ficaram sete dias defasados e passaram a afirmar o contrário do
código em dois pontos — a regra da falta justificada e a tabela onde fica a
presença do grupo. Ninguém percebeu porque nada conferia.

Estes testes conferem só o que dá para conferir sozinho: contagens, listas de
rotas e nomes de tabela. Texto em prosa continua sendo responsabilidade de
quem escreve, mas o que é número não envelhece mais em silêncio.
"""

import pathlib
import re

import pytest

import app as modulo_app
from models import db

RAIZ = pathlib.Path(modulo_app.__file__).parent
README = RAIZ / "README.md"
DOCS = RAIZ / "docs"


def ler(caminho):
    return caminho.read_text(encoding="utf-8")


def rotas_reais(app):
    """Endereços registrados, com os parâmetros normalizados para <id>."""
    return {
        re.sub(r"<[^>]+>", "<id>", str(regra.rule))
        for regra in app.url_map.iter_rules()
        if regra.endpoint != "static"
    }


# ----------------------------------------------------------------------
# Os quatro documentos existem e estão ligados entre si
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "arquivo",
    ["ARQUITETURA.md", "BANCO_DE_DADOS.md", "CASOS_DE_USO.md", "REQUISITOS.md"],
)
def test_documento_existe_e_e_citado_pelo_readme(arquivo):
    caminho = DOCS / arquivo
    assert caminho.exists(), f"docs/{arquivo} sumiu"
    assert f"docs/{arquivo}" in ler(README), f"o README não aponta para {arquivo}"


# ----------------------------------------------------------------------
# Contagens
# ----------------------------------------------------------------------


def test_o_readme_diz_quantos_testes_existem_de_verdade():
    quantos = 0
    for arquivo in (RAIZ / "tests").glob("test_*.py"):
        quantos += len(re.findall(r"^def test_", ler(arquivo), re.M))

    texto = ler(README)
    declarado = re.search(r"\*\*(\d+) testes\*\*", texto)
    assert declarado, "o README não diz mais quantos testes existem"
    # A contagem por 'def test_' ignora os parametrize, então o número
    # publicado é maior. O que não pode é o README ficar para trás.
    assert int(declarado.group(1)) >= quantos, (
        f"o README fala em {declarado.group(1)} testes, mas já existem pelo "
        f"menos {quantos} funções de teste"
    )


def test_o_readme_diz_quantos_templates_existem():
    quantos = len(list((RAIZ / "templates").glob("*.html")))
    achado = re.search(r"# (\d+) templates Jinja", ler(README))
    assert achado, "a árvore de arquivos não diz mais quantos templates existem"
    assert int(achado.group(1)) == quantos


def test_o_readme_diz_quantos_arquivos_de_teste_existem():
    quantos = len(list((RAIZ / "tests").glob("test_*.py")))
    achado = re.search(r"(\d+) testes em (\d+) arquivos", ler(README))
    assert achado, "a árvore de arquivos não diz mais quantos arquivos de teste existem"
    assert int(achado.group(2)) == quantos


# ----------------------------------------------------------------------
# Rotas
# ----------------------------------------------------------------------


def test_toda_rota_do_sistema_esta_no_readme(app):
    texto = ler(README)
    documentadas = set(re.findall(r"`(/[a-z0-9/<>_-]*)`", texto))
    documentadas |= {r for r in re.findall(r"`?(/api/[a-z/]+)`?", texto)}

    faltando = sorted(rotas_reais(app) - documentadas)
    assert not faltando, f"rotas sem documentação no README: {faltando}"


def test_o_readme_nao_promete_rota_que_nao_existe(app):
    texto = ler(README)
    reais = rotas_reais(app)
    documentadas = {
        d
        for d in re.findall(r"`(/[a-z0-9/<>_-]+)`", texto)
        if not d.startswith("/static")
    }

    inventadas = sorted(documentadas - reais)
    assert not inventadas, f"o README cita rotas que não existem: {inventadas}"


# ----------------------------------------------------------------------
# Banco de dados
# ----------------------------------------------------------------------


def test_toda_tabela_do_sistema_aparece_no_readme():
    tabelas = {t for t in db.metadata.tables}
    texto = ler(README)
    faltando = sorted(t for t in tabelas if f"`{t}`" not in texto)
    assert not faltando, f"tabelas sem menção no README: {faltando}"


def test_a_tabela_morta_continua_documentada_como_morta():
    """`presencas` está no banco e não é usada. Enquanto for assim, diga."""
    assert "presencas" not in db.metadata.tables, (
        "a tabela presencas voltou a ser usada: atualize README e ARQUITETURA, "
        "que hoje dizem que ela está morta"
    )
    assert "não é usada" in ler(README)
    assert "presencas" in ler(DOCS / "ARQUITETURA.md")


# ----------------------------------------------------------------------
# As regras que já foram documentadas ao contrário
# ----------------------------------------------------------------------


def test_a_documentacao_nao_diz_que_falta_justificada_conta_como_falta():
    """Foi o que ela dizia por sete dias, e é o oposto do sistema."""
    errado = "conta como falta nos números"
    for arquivo in [README, DOCS / "REQUISITOS.md", DOCS / "CASOS_DE_USO.md"]:
        assert errado not in ler(arquivo), (
            f"{arquivo.name} voltou a dizer que a falta justificada conta como "
            "falta; ela conta como atendimento realizado"
        )


def test_a_documentacao_nao_diz_que_ausencia_espera_o_dia_da_sessao():
    errado = "Presença e falta só são aceitas a partir do dia"
    for arquivo in [README, DOCS / "CASOS_DE_USO.md"]:
        assert errado not in ler(arquivo), (
            f"{arquivo.name} voltou a dizer que a ausência espera o dia; ela "
            "pode ser lançada antes"
        )


@pytest.mark.parametrize(
    "assunto",
    ["triagem", "alta", "reativ", "cartão cidadão", "BrasilAPI", "reposição"],
)
def test_o_readme_cobre_o_que_o_sistema_faz(assunto):
    """Nenhum destes aparecia antes da revisão, e todos existem no sistema."""
    assert assunto.lower() in ler(README).lower(), f"o README não menciona {assunto}"
