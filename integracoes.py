"""Integrações com serviços de fora do FisioBase.

Hoje existe uma: a BrasilAPI, de onde vêm os feriados nacionais.

A tabela `feriados` já existia desde o esquema original — o comentário lá
dizia "Nacionais podem vir da BrasilAPI" — e cinco partes do sistema pulam
essas datas ao montar a agenda. O que faltava era o caminho até a API.

Duas escolhas deliberadas aqui:

1. Usa `urllib`, da biblioteca padrão, em vez de `requests`. O sistema roda
   no Vercel, e cada dependência a mais é mais uma coisa que pode quebrar a
   publicação. Para uma chamada GET que devolve JSON, a biblioteca padrão
   basta.

2. Os erros têm nome (`IntegracaoIndisponivel`) e a tela os trata. A
   importação é uma ação manual do administrador: se a BrasilAPI estiver
   fora do ar, a tela avisa e o resto do sistema segue funcionando com os
   feriados que já foram importados antes. Nenhuma tela do dia a dia
   depende desta API.

Nenhum dado de paciente sai daqui: a única coisa enviada é o ano.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date

# A BrasilAPI é pública e não pede cadastro nem chave.
URL_DOS_FERIADOS = "https://brasilapi.com.br/api/feriados/v1/{ano}"
# Se não responder nesse prazo, desistimos: a tela não pode ficar pendurada
# esperando um serviço de fora.
SEGUNDOS_DE_ESPERA = 8
# A clínica não monta agenda para um passado distante nem para um futuro
# remoto; a própria BrasilAPI também tem limites.
ANO_MINIMO = 2003
ANO_MAXIMO = 2078


class IntegracaoIndisponivel(Exception):
    """A API de fora não respondeu, ou respondeu algo que não dá para usar.

    Quem chama trata isso como "tente de novo mais tarde", nunca como um
    erro do sistema: o problema está do outro lado.
    """


def _baixar(url: str) -> bytes:
    """Busca o conteúdo de uma URL.

    Fica numa função sozinha de propósito: é o único ponto que toca a rede,
    e é ele que os testes substituem para não depender da internet.
    """
    requisicao = urllib.request.Request(
        url,
        headers={"User-Agent": "FisioBase/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(requisicao, timeout=SEGUNDOS_DE_ESPERA) as resposta:
        return resposta.read()


def buscar_feriados_nacionais(ano: int) -> list[dict]:
    """Devolve os feriados nacionais do ano, já em data/nome.

    A BrasilAPI responde uma lista assim:

        [{"date": "2027-04-21", "name": "Tiradentes", "type": "national"}]

    Devolvemos `[{"data": date(2027, 4, 21), "nome": "Tiradentes"}]`, já
    ordenado, para o resto do sistema não precisar saber o formato de lá.

    Levanta IntegracaoIndisponivel se a API não responder, demorar demais ou
    devolver algo fora do formato esperado.
    """
    if not isinstance(ano, int) or not ANO_MINIMO <= ano <= ANO_MAXIMO:
        raise ValueError(f"Ano fora do intervalo aceito ({ANO_MINIMO}–{ANO_MAXIMO}).")

    try:
        bruto = _baixar(URL_DOS_FERIADOS.format(ano=ano))
    except urllib.error.HTTPError as erro:
        if erro.code == 404:
            raise IntegracaoIndisponivel(
                f"A BrasilAPI não tem os feriados de {ano}."
            ) from erro
        raise IntegracaoIndisponivel(
            f"A BrasilAPI respondeu com erro {erro.code}."
        ) from erro
    except (urllib.error.URLError, OSError) as erro:
        # Inclui falta de rede e estouro do prazo de espera.
        raise IntegracaoIndisponivel(
            "Não foi possível falar com a BrasilAPI agora."
        ) from erro

    try:
        conteudo = json.loads(bruto)
    except (ValueError, UnicodeDecodeError) as erro:
        raise IntegracaoIndisponivel(
            "A BrasilAPI respondeu algo que não é JSON."
        ) from erro

    if not isinstance(conteudo, list):
        raise IntegracaoIndisponivel("A BrasilAPI respondeu num formato inesperado.")

    feriados = []
    for item in conteudo:
        if not isinstance(item, dict):
            continue
        texto = str(item.get("date", "")).strip()
        nome = str(item.get("name", "")).strip()
        if not texto or not nome:
            continue
        try:
            dia = date.fromisoformat(texto)
        except ValueError:
            # Uma data estranha não invalida as outras: pulamos só ela.
            continue
        if dia.year != ano:
            continue
        feriados.append({"data": dia, "nome": nome[:150]})

    if not feriados:
        raise IntegracaoIndisponivel(
            f"A BrasilAPI não devolveu nenhum feriado utilizável para {ano}."
        )

    feriados.sort(key=lambda f: f["data"])
    return feriados
