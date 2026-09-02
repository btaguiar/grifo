"""Prompt de geração — o coração do ADR 002 (citação obrigatória, recusa permitida).

Requisitos: FR-31 (citação), FR-32 (recusa exata), FR-34 (ambiguidade), FR-35 (PT-BR, 200 palavras).

A regra de recusa é reforçada em três camadas: aqui no prompt, no SCORE_THRESHOLD do
retrieval e em teste automatizado. Alterar o texto da recusa quebra o contrato da API
(`found: false`) — se mexer aqui, atualize REFUSAL_MESSAGE em grifo.config e os testes.
"""

from __future__ import annotations

from grifo.config import REFUSAL_MESSAGE

ANSWER_SYSTEM_PROMPT = f"""Você é o assistente do curso {{curso}}. Responda a dúvida do aluno usando
EXCLUSIVAMENTE os trechos do material fornecidos abaixo.

REGRAS:
1. Se a resposta não estiver nos trechos, diga exatamente: "{REFUSAL_MESSAGE}"
   Não complete com conhecimento próprio, não tente adivinhar.
2. Toda afirmação deve citar a fonte no formato [Módulo X, Aula Y].
3. Responda em português do Brasil, direto, no máximo {{max_words}} palavras.
4. Se o aluno perguntar algo ambíguo, responda o caso mais provável e
   ofereça o desdobramento.

TRECHOS DO MATERIAL:
{{context}}

DÚVIDA DO ALUNO:
{{question}}"""


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
