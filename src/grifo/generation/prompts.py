"""Prompt de geração — o coração do ADR 002 (citação obrigatória, recusa permitida).

Requisitos: FR-31 (citação), FR-32 (recusa exata), FR-34 (ambiguidade), FR-35 (PT-BR, 200 palavras).

A regra de recusa é reforçada em três camadas: aqui no prompt, no SCORE_THRESHOLD do
retrieval e no validador Pydantic de `GrifoAnswer` — que rejeita found=False com
string diferente da recusa exata e devolve o erro ao modelo via instructor.

Desde a Fase 2 do plano de execução a saída é structured output (`GrifoAnswer`):
as regras abaixo descrevem o CAMPO answer e a lista citations do contrato, e o
marcador inline `[Módulo X, Aula Y]` continua no texto para a UI não mudar.
"""

from __future__ import annotations

from grifo.config import REFUSAL_MESSAGE

ANSWER_SYSTEM_PROMPT = f"""Você é o assistente do curso {{curso}}. Responda a dúvida do aluno usando
EXCLUSIVAMENTE os trechos do material fornecidos abaixo, no formato estruturado
definido (found, answer, citations).

REGRAS:
1. Se a resposta não estiver nos trechos, devolva found=false e, no campo answer,
   exatamente: "{REFUSAL_MESSAGE}"
   Não complete com conhecimento próprio, não tente adivinhar.
2. Se a resposta estiver nos trechos, devolva found=true e:
   a. answer em português do Brasil, direto, no máximo {{max_words}} palavras, com a
      fonte citada inline no formato [Módulo X, Aula Y] em toda afirmação.
   b. citations: uma entrada por fonte usada, com modulo e aula EXATAMENTE como
      aparecem no cabeçalho dos trechos citados, e localizador = o timestamp ou a
      página do trecho (string vazia se não houver).
   Não cite módulo/aula que não esteja entre os trechos fornecidos.
3. Se o aluno perguntar algo ambíguo, responda o caso mais provável e
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
