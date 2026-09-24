"""Contraste dos textos de apoio, e o aviso que dá tempo de ser lido.

Os cinzas do sistema ficavam entre 1,8:1 e 3,9:1 sobre o fundo claro —
legíveis num monitor bom, invisíveis nos outros. O mínimo da norma de
acessibilidade (WCAG AA) é 4,5:1 para texto normal.

Aqui o contraste é calculado de verdade a partir do CSS publicado, para que
um cinza claro não volte sem ninguém perceber.
"""

import pathlib
import re

import pytest

import app as modulo_app

CSS = pathlib.Path(modulo_app.__file__).parent / "static" / "css" / "style.css"
JS = pathlib.Path(modulo_app.__file__).parent / "static" / "js" / "app.js"

PAPEL = "#f7faf9"
NAVY = "#12313d"
MINIMO = 4.5


def _rgb(cor):
    cor = cor.lstrip("#")
    if len(cor) == 3:
        cor = "".join(c * 2 for c in cor)
    return tuple(int(cor[i : i + 2], 16) for i in (0, 2, 4))


def _luminancia(cor):
    def canal(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(c) for c in _rgb(cor))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(frente, fundo):
    a, b = _luminancia(frente), _luminancia(fundo)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def cor_da_regra(seletor, propriedade="color"):
    """Lê o valor de uma propriedade dentro de um seletor do CSS."""
    texto = CSS.read_text(encoding="utf-8")
    bloco = re.search(
        rf"(?:^|\n)\s*{re.escape(seletor)}\s*(?:,[^{{]*)?\{{(.*?)\}}",
        texto,
        re.S,
    )
    assert bloco, f"não achei o seletor {seletor} no CSS"
    valor = re.search(rf"{propriedade}:\s*(#[0-9a-fA-F]{{3,8}})", bloco.group(1))
    assert valor, f"{seletor} não declara {propriedade} em hexadecimal"
    return valor.group(1)


def test_o_contraste_e_calculado_certo():
    """Sanidade do próprio medidor, antes de confiar nele."""
    assert round(contraste("#000000", "#ffffff"), 2) == 21.0
    assert round(contraste("#ffffff", "#ffffff"), 2) == 1.0


# ----------------------------------------------------------------------
# Textos de apoio
# ----------------------------------------------------------------------

SOBRE_FUNDO_CLARO = [
    ".breadcrumb",
    # .eyebrow sem sufixo vive sobre a faixa escura e usa a cor de destaque;
    # a versão --muted é a que aparece sobre o fundo claro dos painéis.
    ".eyebrow--muted",
    ".muted-cell",
    ".panel-count",
    ".panel-note",
    ".field-hint",
    ".stat-label",
]


@pytest.mark.parametrize("seletor", SOBRE_FUNDO_CLARO)
def test_texto_de_apoio_passa_do_minimo(seletor):
    cor = cor_da_regra(seletor)
    razao = contraste(cor, PAPEL)
    assert razao >= MINIMO, f"{seletor} está em {cor} — {razao:.2f}:1, abaixo de 4,5"


def test_variavel_muted_passa_do_minimo():
    cor = re.search(r"--muted:\s*(#[0-9a-fA-F]{3,6})", CSS.read_text(encoding="utf-8"))
    assert cor, "a variável --muted sumiu"
    assert contraste(cor.group(1), PAPEL) >= MINIMO


def test_menu_da_lateral_passa_sobre_a_navy():
    """Na lateral escura o texto precisa clarear, não escurecer."""
    assert contraste(cor_da_regra(".nav-label"), NAVY) >= MINIMO


# ----------------------------------------------------------------------
# Etiquetas de situação
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "situacao",
    ["compareceu", "faltou", "justificada", "cancelado", "agendado", "confirmado"],
)
def test_etiqueta_de_situacao_e_legivel(situacao):
    seletor = f".situacao-badge--{situacao}"
    frente = cor_da_regra(seletor, "color")
    fundo = cor_da_regra(seletor, "background")
    razao = contraste(frente, fundo)
    assert razao >= MINIMO, f"{seletor}: {frente} sobre {fundo} = {razao:.2f}:1"


def test_falta_e_vermelha_e_justificada_nao():
    vermelho = cor_da_regra(".situacao-badge--faltou", "color")
    justificada = cor_da_regra(".situacao-badge--justificada", "color")
    r, g, b = _rgb(vermelho)
    assert r > g + 60 and r > b + 60, f"a falta não está em vermelho: {vermelho}"
    assert vermelho != justificada


# ----------------------------------------------------------------------
# O aviso flutuante
# ----------------------------------------------------------------------


def test_o_aviso_dura_mais_que_os_quatro_segundos_de_antes():
    fonte = JS.read_text(encoding="utf-8")
    tempo = re.search(r"TEMPO_DO_AVISO\s*=\s*(\d+)", fonte)
    assert tempo, "o tempo do aviso deixou de ter nome próprio"
    assert int(tempo.group(1)) >= 8000, "curto demais para uma mensagem com números"


def test_o_aviso_pode_ser_fechado_e_para_com_o_mouse_em_cima():
    fonte = JS.read_text(encoding="utf-8")
    assert "flash-fechar" in fonte, "sumiu o botão de fechar o aviso"
    assert "mouseenter" in fonte and "mouseleave" in fonte
    assert "focusin" in fonte, "quem usa teclado também precisa segurar o aviso"


def test_o_botao_de_fechar_tem_estilo():
    assert ".flash-fechar" in CSS.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# A tabela de grupos
# ----------------------------------------------------------------------


def test_a_coluna_do_nome_do_grupo_tem_piso_de_largura():
    """Os botões ocupavam um terço da tabela e o nome quebrava em 5 linhas."""
    texto = CSS.read_text(encoding="utf-8")
    assert ".tabela-grupos td:first-child" in texto
    assert "min-width: 250px" in texto


def test_a_lista_de_grupos_usa_a_tabela_com_nome_proprio():
    modelo = (
        pathlib.Path(modulo_app.__file__).parent / "templates" / "grupos_lista.html"
    )
    assert 'class="tabela-grupos"' in modelo.read_text(encoding="utf-8")
