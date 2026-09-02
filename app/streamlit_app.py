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
            continue
        if msg["found"]:
            st.write(msg["content"])
            with st.expander("Fontes", expanded=False):
                for fonte in msg["sources"]:
                    linha = (
                        f"**Módulo** {fonte['modulo']} · **Aula** {fonte['aula']} · "
                        f"score `{fonte['score']}`"
                    )
                    link = video_link(fonte.get("timestamp"))
                    if link:
                        linha += f" · [abrir no minuto {fonte['timestamp']}]({link})"
                    elif fonte.get("timestamp"):
                        linha += f" · referência: {fonte['timestamp']}"
                    st.markdown(linha)
        else:
            # FR-63: recusa é uma resposta legítima — destaque amarelo, não vermelho de erro.
            st.warning(msg["content"])

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
                    timeout=30.0,
                )
                r.raise_for_status()
                resposta = r.json()
            except httpx.HTTPError:
                resposta = None
                st.error(
                    "Não consegui falar com o serviço do Grifo. "
                    "Confira se a API está no ar (docker compose up)."
                )

        if resposta:
            if resposta["found"]:
                st.write(resposta["answer"])
                with st.expander("Fontes", expanded=True):
                    for fonte in resposta["sources"]:
                        linha = (
                            f"**Módulo** {fonte['modulo']} · **Aula** {fonte['aula']} · "
                            f"score `{fonte['score']}`"
                        )
                        link = video_link(fonte.get("timestamp"))
                        if link:
                            linha += f" · [abrir no minuto {fonte['timestamp']}]({link})"
                        elif fonte.get("timestamp"):
                            linha += f" · referência: {fonte['timestamp']}"
                        st.markdown(linha)
            else:
                st.warning(resposta["answer"])
                st.caption("Prefiro dizer que não sei a inventar uma resposta.")
            st.session_state.mensagens.append(
                {
                    "role": "assistant",
                    "content": resposta["answer"],
                    "found": resposta["found"],
                    "sources": resposta["sources"],
                }
            )
