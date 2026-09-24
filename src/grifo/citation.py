"""A citação: como ela é escrita, como se reconhece uma, e o link que ela vira.

O FR-62 existia só na UI e com UMA `VIDEO_BASE_URL` para o curso inteiro, o que
pressupõe um player por curso. Material publicado em vídeo é o contrário disso: cada
aula tem a sua URL. A URL passa a ser metadado da aula (DC-1, `fonte_url`), e o link
com timestamp é montado aqui — um lugar só, usado pela chain (para todo cliente da API
receber pronto) e pela UI.

O formato da citação também mora aqui, e pelo mesmo motivo: a expressão regular que
reconhece `[Módulo X, Aula Y]` estava duplicada na chain e no `run_eval.py`. Duas
cópias da mesma regra é uma que se esquece de atualizar — e a que se esquece é a do
eval, que mediria citação boa como ausente.
"""

from __future__ import annotations

import re

#: Citação bem formada, com autor opcional: `[Módulo X, Aula Y]` ou
#: `[Módulo X, Aula Y — Fulano]`. A vírgula separa módulo de aula, então nenhum dos
#: dois pode contê-la; o autor vem depois do travessão e vai até o colchete.
CITACAO_RE = re.compile(r"\[Módulo [^\],]+, Aula [^\],\]]+(?: — [^\]]+)?\]")


def formatar_citacao(modulo: str, aula: str, autor: str | None = None) -> str:
    """O texto da citação — um lugar só, porque o eval mede o que a chain escreve."""
    corpo = f"Módulo {modulo}, Aula {aula}"
    return f"[{corpo} — {autor}]" if autor else f"[{corpo}]"


def timestamp_para_segundos(timestamp: str) -> int:
    """ "HH:MM:SS" ou "MM:SS" -> segundos, para o parâmetro `?t=` do player."""
    partes = [int(p) for p in timestamp.split(":")]
    while len(partes) < 3:
        partes.insert(0, 0)
    horas, minutos, segundos = partes
    return horas * 3600 + minutos * 60 + segundos


def link_com_timestamp(fonte_url: str | None, timestamp: str | None) -> str | None:
    """A URL da aula apontando o minuto do trecho; a URL crua quando não há timestamp.

    Sem `fonte_url` não há link — e é o caso de PDF e markdown, que localizam por
    página. `&t=` quando a URL já tem query (`watch?v=...`), `?t=` quando não tem.
    """
    if not fonte_url:
        return None
    if not timestamp:
        return fonte_url
    separador = "&" if "?" in fonte_url else "?"
    return f"{fonte_url}{separador}t={timestamp_para_segundos(timestamp)}"
