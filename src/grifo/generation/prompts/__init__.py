"""Prompts versionados em arquivos (plano de execução, Fase 5).

O histórico `0.43 → 0.795 → 0.045` de alucinação é o efeito de trocar uma vírgula de
prompt movendo números sem rastro. Os prompts agora vivem em `.txt` ao lado deste
módulo e são carregados em tempo de import; o SHA-256 de cada um acompanha o bloco
`config` dos `metricas_*.json`, e um teste unitário trava o hash de referência —
mudar prompt exige atualizar o hash, o que torna a mudança decisão explícita.

O texto da recusa aparece literal no `answer_system.txt`; o acoplamento com
`REFUSAL_MESSAGE` é guardado pelo teste que exige a recusa exata no prompt formatado
(mudar uma sem a outra reprova o build).

`answer_system.txt` interpola `{curso}`, `{max_words}`, `{context}` e `{question}` no
momento da chamada; `judge.txt` interpola `{c}`, `{q}` e `{a}` — o mesmo esquema de
f-string de antes, só que em arquivo.
"""

from __future__ import annotations

from importlib import resources

from grifo.config import REFUSAL_MESSAGE  # noqa: F401  (guardado pelos testes)


def _carregar(nome: str) -> str:
    """Lê o prompt versionado — falha alto se o arquivo sumiu ou mudou de nome."""
    return resources.files("grifo.generation.prompts").joinpath(nome).read_text(encoding="utf-8")


ANSWER_SYSTEM_PROMPT = _carregar("answer_system.txt")

#: Prompt do juiz de alucinação. CALIBRADO contra eval/judge_calibration.jsonl.
#: A versão anterior perguntava "contém ALGUMA afirmação não sustentada?" e reprovava
#: paráfrase fiel. Num RAG quase toda resposta é reformulação, entao aquilo inflou a
#: taxa medida para 79,5%. Esta versao separa "reformular" de "inventar fato novo".
JUDGE_PROMPT = _carregar("judge.txt")


def format_context(chunks) -> str:
    """Serializa os chunks recuperados no bloco {context} do prompt.

    Cada trecho expõe módulo, aula e o localizador (timestamp ou página) de forma
    legível: é daqui que o modelo tira a citação `[Módulo X, Aula Y]` de FR-31.
    """
    partes = []
    for i, chunk in enumerate(chunks, start=1):
        md = chunk["metadata"]
        localizacao = f"Módulo: {md['modulo']} | Aula: {md['aula']}"
        if md.get("timestamp_inicio"):
            localizacao += f" | Timestamp: {md['timestamp_inicio']}"
        if md.get("pagina") is not None:
            localizacao += f" | Página: {md['pagina']}"
        partes.append(f"[{i}] {localizacao}\n{chunk['text']}")
    return "\n\n".join(partes)
