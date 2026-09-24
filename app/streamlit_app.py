"""UI de chat em Streamlit (FR-60 a FR-63).

Requisitos de demo: historico de sessao, fontes com modulo/aula/score abaixo da resposta,
timestamp clicavel para o minuto do video, e estado de recusa visualmente distinto.

O estado de recusa (FR-63) e o momento mais forte do video de 2 min. Nao trate como caso
de erro: e uma resposta legitima e deve parecer intencional na tela.

Aponta para a API via a variavel de ambiente API_URL.
"""

from __future__ import annotations

import os
import uuid

import httpx
import streamlit as st

#: 127.0.0.1 pelo mesmo motivo do QDRANT_URL: ver EVALUATION.md 4.5.
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
CURSO = os.environ.get("CURSO_NOME", "Curso Exemplo")
VIDEO_BASE_URL = os.environ.get("VIDEO_BASE_URL", "")
#: Era 30s fixo, e a primeira pergunta no setup local (qwen 7B em CPU) levou 30,3s em
#: 2026-09-10: a UI desistia antes da resposta chegar. Remoto responde em ~3-7s.
API_TIMEOUT = float(os.environ.get("API_TIMEOUT", "90"))


def timestamp_to_seconds(timestamp: str) -> int:
    """ "HH:MM:SS" ou "MM:SS" -> segundos, para o parâmetro ?t= do player."""
    partes = [int(p) for p in timestamp.split(":")]
    while len(partes) < 3:
        partes.insert(0, 0)
    h, m, s = partes
    return h * 3600 + m * 60 + s


def video_link(timestamp: str | None) -> str | None:
    """Link para o minuto do vídeo quando há player configurado (FR-62)."""
    if not timestamp or not VIDEO_BASE_URL:
        return None
    return f"{VIDEO_BASE_URL.rstrip('/')}?t={timestamp_to_seconds(timestamp)}"


def agrupar_por_aula(sources: list[dict]) -> list[dict]:
    """Uma linha por aula, não por trecho.

    A API devolve um item por chunk recuperado, e dois chunks da mesma aula viravam
    duas linhas idênticas "Módulo 2 · Aula 4" na tela. Aqui a aula fica com o melhor
    score e o timestamp do trecho que o obteve; `cited` vale se QUALQUER trecho dela
    foi citado. Citadas primeiro, depois por score.
    """
    aulas: dict[tuple[str, str], dict] = {}
    for fonte in sources:
        chave = (fonte["modulo"], fonte["aula"])
        atual = aulas.get(chave)
        if atual is None:
            aulas[chave] = {**fonte, "cited": bool(fonte.get("cited")), "trechos": 1}
            continue
        atual["trechos"] += 1
        atual["cited"] = atual["cited"] or bool(fonte.get("cited"))
        if fonte["score"] > atual["score"]:
            atual["score"] = fonte["score"]
            atual["timestamp"] = fonte.get("timestamp")
    return sorted(aulas.values(), key=lambda f: (not f["cited"], -f["score"]))


def linha_fonte(fonte: dict) -> str:
    """Markdown de uma aula na lista de fontes."""
    linha = f"**Módulo** {fonte['modulo']} · **Aula** {fonte['aula']} · score `{fonte['score']}`"
    if fonte.get("trechos", 1) > 1:
        linha += f" · {fonte['trechos']} trechos"
    link = video_link(fonte.get("timestamp"))
    if link:
        linha += f" · [abrir no minuto {fonte['timestamp']}]({link})"
    elif fonte.get("timestamp"):
        linha += f" · referência: {fonte['timestamp']}"
    return linha


def mensagem_de_falha(erro: httpx.HTTPError) -> str:
    """O que dizer quando a pergunta não volta — sem culpar a peça errada.

    Tudo caía em "confira se a API está no ar", inclusive o 500 de provedor LLM
    recusando a requisição, com a API perfeitamente no ar.
    """
    if isinstance(erro, httpx.TimeoutException):
        return (
            f"A resposta passou de {API_TIMEOUT:.0f}s. Com modelo local isso acontece; "
            "tente de novo ou aumente API_TIMEOUT."
        )
    if isinstance(erro, httpx.HTTPStatusError):
        return (
            f"A API respondeu com erro {erro.response.status_code}. "
            "O log dela diz o motivo — em geral, o provedor do LLM."
        )
    return "Não consegui falar com o serviço do Grifo. Confira se a API está no ar."


def render_resposta(msg: dict, expandir_fontes: bool) -> None:
    """Desenha uma resposta do assistente — a mesma função para o histórico e a nova.

    Eram dois blocos copiados, e já tinham divergido: a legenda da recusa só aparecia
    na mensagem nova e sumia quando a conversa era redesenhada.
    """
    if not msg["found"]:
        # FR-63: recusa é uma resposta legítima — destaque amarelo, não vermelho de erro.
        st.warning(msg["content"])
        st.caption("Prefiro dizer que não sei a inventar uma resposta.")
        return

    st.write(msg["content"])
    aulas = agrupar_por_aula(msg["sources"])
    citadas = [f for f in aulas if f["cited"]]
    consultadas = [f for f in aulas if not f["cited"]]
    with st.expander("Fontes", expanded=expandir_fontes):
        if not citadas:
            # Sem `cited` (API anterior ao campo), não há o que separar.
            for fonte in aulas:
                st.markdown(linha_fonte(fonte))
            return
        st.caption("Citadas na resposta")
        for fonte in citadas:
            st.markdown(linha_fonte(fonte))
        if consultadas:
            st.caption("Também consultadas, sem citação")
            for fonte in consultadas:
                st.markdown(f":gray[{linha_fonte(fonte)}]")


st.set_page_config(page_title="Grifo", page_icon="📚")

if "mensagens" not in st.session_state:
    st.session_state.mensagens = []
if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex

st.title("Grifo")
st.caption(
    f"Assistente do curso **{CURSO}** — responde só com o material oficial, sempre citando a fonte."
)

for msg in st.session_state.mensagens:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.write(msg["content"])
        else:
            render_resposta(msg, expandir_fontes=False)

pergunta = st.chat_input("Qual é a sua dúvida sobre o curso?")

if pergunta:
    st.session_state.mensagens.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.write(pergunta)

    with st.chat_message("assistant"):
        with st.spinner("Consultando o material do curso..."):
            try:
                r = httpx.post(
                    f"{API_URL}/ask",
                    json={
                        "question": pergunta,
                        "session_id": st.session_state.session_id,
                        "curso": CURSO,
                    },
                    timeout=API_TIMEOUT,
                )
                r.raise_for_status()
                resposta = r.json()
            except httpx.HTTPError as erro:
                resposta = None
                st.error(mensagem_de_falha(erro))

        if resposta:
            msg = {
                "role": "assistant",
                "content": resposta["answer"],
                "found": resposta["found"],
                "sources": resposta["sources"],
            }
            render_resposta(msg, expandir_fontes=True)
            st.session_state.mensagens.append(msg)
