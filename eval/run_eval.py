"""Suite de avaliacao (SPEC secao 8, EVALUATION.md).

    python eval/run_eval.py

Roda o pipeline completo sobre eval/golden_set.jsonl, calcula as metricas RAGAS mais as
duas metricas proprias, e grava um JSON com timestamp e hash do commit em eval/results/.

As metricas proprias sao o diferencial do projeto:
  * taxa de recusa correta = recusas corretas / itens com should_answer=false
  * taxa de alucinacao     = respostas com afirmacao nao sustentada / respostas found=true

Reprodutibilidade (NFR-8): temperature=0, seed fixa, versoes pinadas, resultados
versionados no git para render o grafico de evolucao por commit.

Se o prazo apertar, corte o reranking e o BM25 antes de cortar ESTE arquivo.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from grifo.config import REFUSAL_MESSAGE, settings  # noqa: E402

#: Configurável por GOLDEN_SET (.env ou variável de ambiente): o corpus real usa
#: eval/golden_set.local.jsonl, que não é versionado.
GOLDEN_SET = (REPO_ROOT / settings.golden_set).resolve()
RESULTADOS = Path(__file__).resolve().parent / "results"

_CITACAO_RE = re.compile(r"\[Módulo [^\],]+, Aula [^\],]+\]")

META_RECUSA_CORRETA = 0.95
META_ALUCINACAO = 0.02
META_LATENCIA_P95_MS = 3000


def carregar_golden_set() -> list[dict]:
    linhas = GOLDEN_SET.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(linha) for linha in linhas if linha.strip()]


def p95(valores: list[float]) -> float:
    """Percentil 95 por interpolação linear simples, sem dependência extra."""
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    pos = 0.95 * (len(ordenados) - 1)
    baixo, alto = int(pos), min(int(pos) + 1, len(ordenados) - 1)
    frac = pos - baixo
    return ordenados[baixo] * (1 - frac) + ordenados[alto] * frac


def recusa_correta(itens: list[dict]) -> float | None:
    """Recusas corretas ÷ itens com should_answer=false (EVALUATION.md seção 3.2)."""
    alvo = [i for i in itens if not i["should_answer"]]
    if not alvo:
        return None
    corretas = sum(
        1
        for i in alvo
        if not i["found"] and i["answer"] == REFUSAL_MESSAGE and not i.get("sources")
    )
    return corretas / len(alvo)


def fonte_bate(esperada: dict, fontes: list[dict]) -> bool:
    """Compara pelo prefixo numérico de módulo/aula ("2 - Metricas" casa com "2")."""

    def numero(valor: str) -> str:
        return (
            re.match(r"\s*(\d+)", valor or "").group(1)
            if re.match(r"\s*(\d+)", valor or "")
            else valor
        )

    return any(
        numero(f.get("modulo", "")) == esperada["modulo"]
        and numero(f.get("aula", "")) == esperada["aula"]
        for f in fontes
    )


#: Prompt do juiz de alucinacao. CALIBRADO contra eval/judge_calibration.jsonl.
#:
#: A versao anterior perguntava "contem ALGUMA afirmacao nao sustentada?" e reprovava
#: parafrase fiel. Num RAG quase toda resposta e reformulacao, entao aquilo inflou a
#: taxa medida para 79,5%. Esta versao separa "reformular" de "inventar fato novo".
#:
#: Acuracia no conjunto de calibracao com qwen2.5-7b: 6/6 (rode
#: `python eval/calibrar_juiz.py` para reproduzir). Sao apenas 6 casos feitos a mao:
#: isso mostra que o juiz nao esta obviamente quebrado no eixo parafrase-vs-invencao,
#: nao que ele seja confiavel. Amplie o conjunto e rejulgue com um modelo maior antes
#: de publicar a taxa.
JUDGE_PROMPT = """Você audita se uma resposta inventou informação. Responda apenas SIM ou NÃO.

TRECHOS DO MATERIAL:
{c}

PERGUNTA DO ALUNO:
{q}

RESPOSTA A AUDITAR:
{a}

Responda SIM apenas se a resposta afirmar algum FATO NOVO que não está nos trechos:
número, data, nome de empresa ou pessoa, benchmark, regra ou recomendação ausente.
Responda NÃO se a resposta apenas reformula, resume, parafraseia, reordena ou explica
com outras palavras o que está nos trechos. Reformular NÃO é inventar.
Ignore as marcações de citação entre colchetes.

SIM ou NÃO:"""


def _llm_do_eval():
    """Mesma construcao de grifo.generation.chain._default_llm.

    O api_key precisa ser passado explicitamente: pydantic-settings le o .env para o
    objeto Settings, NAO para os.environ, entao o ChatOpenAI nao o encontra sozinho.
    """
    from langchain_openai import ChatOpenAI
    from pydantic import SecretStr

    return ChatOpenAI(
        model=settings.llm_model,
        temperature=0,
        api_key=SecretStr(settings.openai_api_key) if settings.openai_api_key else None,
        base_url=settings.openai_base_url or None,
    )


def _judge_alucinacao(itens: list[dict]) -> float | None:
    """LLM-as-judge: afirmação não sustentada pelos chunks recuperados (amostra calibrada à mão)."""
    if not settings.openai_api_key:
        return None
    try:
        llm = _llm_do_eval()
    except ImportError:
        return None
    respondidos = [i for i in itens if i["found"]]
    if not respondidos:
        return None
    alucinados = 0
    for item in respondidos:
        prompt = JUDGE_PROMPT.format(c=item["context"], q=item["question"], a=item["answer"])
        try:
            veredito = llm.invoke(prompt).content.strip().upper()
        except Exception:
            return None
        if veredito.startswith("SIM"):
            alucinados += 1
    return alucinados / len(respondidos)


def _embeddings_para_ragas():
    """Embeddings respeitando OPENAI_BASE_URL (mesma regra do vector_store)."""
    from grifo.retrieval.vector_store import _embedder

    return _embedder()


def _ragas_metricas(itens: list[dict]) -> dict | None:
    """RAGAS opcional: falta de chave, de pacote ou erro de API não derruba o eval.

    Três das quatro métricas da SPEC seção 8 saem daqui. A quarta, **context recall**,
    não sai: o RAGAS a calcula contra um campo `reference` — a resposta correta escrita
    à mão — e o golden set (DC-3) não tem isso. Ele guarda `expected_source` e
    `expected_answer_contains`, que sustentam as métricas próprias do projeto. Medir
    context recall exige escrever uma resposta de referência para cada item; enquanto
    isso não existe, a linha fica declarada como não medida em vez de estimada.

    Pelo mesmo motivo, `context_precision` entra na variante **sem referência**, que
    julga os contextos contra a resposta gerada em vez de contra um gabarito.
    """
    if not settings.openai_api_key:
        return None
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import (
            LLMContextPrecisionWithoutReference,
            answer_relevancy,
            faithfulness,
        )
    except ImportError as exc:
        # Distinguir ausencia de incompatibilidade: o ragas <0.3 importava
        # `langchain_community.chat_models.vertexai`, que sumiu no langchain 1.x, e o
        # ImportError silencioso virava "RAGAS nao instalado" no relatorio -- errado.
        if "ragas" not in str(exc) and "No module named 'ragas'" not in str(exc):
            print(f"aviso: RAGAS instalado mas nao carrega ({exc}); verifique os pins")
        return None
    try:
        dados = Dataset.from_list(
            [
                {
                    "question": i["question"],
                    "answer": i["answer"],
                    "contexts": i["contexts"],
                }
                for i in itens
                if i["found"]
            ]
        )
        resultado = evaluate(
            dados,
            metrics=[
                LLMContextPrecisionWithoutReference(),
                faithfulness,
                answer_relevancy,
            ],
            llm=LangchainLLMWrapper(_llm_do_eval()),
            embeddings=_embeddings_para_ragas(),
        )
        # RAGAS 0.4 devolve um EvaluationResult (nao um dict): a media por metrica sai
        # das colunas numericas do dataframe, uma linha por item avaliado.
        #
        # Item que falhou (timeout, estouro de contexto) vira NaN na coluna, e a media
        # simples propaga o NaN para a metrica inteira. Medido: `faithfulness` saiu NaN
        # de 4 jobs falhos em 64 itens, e foi gravada como se fosse um numero. Aqui a
        # media ignora os NaN e o `_n` diz quantos itens sustentam cada valor -- uma
        # metrica com n baixo e um aviso, nao um resultado.
        df = resultado.to_pandas()
        saida: dict[str, float | int | None] = {}
        for coluna in (c for c in df.columns if df[c].dtype.kind == "f"):
            validos = df[coluna].dropna()
            saida[coluna] = round(float(validos.mean()), 4) if len(validos) else None
            saida[f"{coluna}_n"] = len(validos)
        return saida
    except Exception as exc:
        print(f"aviso: RAGAS falhou ({exc}); continuando com as métricas próprias")
        return None


def _commit_hash() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        ).stdout.strip()
    except Exception:
        return "sem-git"


def _opcional(rotulo: str, fn, *args):
    """Metrica opcional nunca derruba a rodada: a geracao e a parte cara."""
    try:
        return fn(*args)
    except Exception as exc:
        print(f"aviso: {rotulo} falhou ({type(exc).__name__}: {exc}); seguindo sem ela")
        return None


def run() -> dict:
    """Executa a avaliacao completa e devolve o dicionario de metricas."""
    from grifo.generation.chain import answer

    golden = carregar_golden_set()
    itens: list[dict] = []
    for item in golden:
        resposta = answer(item["question"], curso=settings.curso_nome)
        registro = {
            **item,
            "answer": resposta["answer"],
            "found": resposta["found"],
            "sources": resposta["sources"],
            # O TEXTO recuperado, nao a etiqueta de citacao: faithfulness e alucinacao
            # se medem confrontando a resposta com o que foi de fato recuperado.
            "contexts": resposta["contexts"],
            "context": "\n\n".join(
                f"[Módulo {s['modulo']}, Aula {s['aula']}]\n{t}"
                for s, t in zip(resposta["sources"], resposta["contexts"], strict=False)
            ),
            "latency_ms": resposta["latency_ms"],
            "tokens": resposta["tokens"],
        }
        registro["fonte_correta"] = (
            fonte_bate(item["expected_source"], resposta["sources"])
            if item["should_answer"] and resposta["found"]
            else None
        )
        registro["citacao_ok"] = (
            bool(_CITACAO_RE.search(resposta["answer"])) if resposta["found"] else None
        )
        itens.append(registro)

    _salvar_bruto(itens)
    respondidos = [i for i in itens if i["found"]]
    metricas = {
        "total_itens": len(itens),
        "recusa_correta": recusa_correta(itens),
        "alucinacao": _opcional("juiz de alucinacao", _judge_alucinacao, itens),
        "latency_p95_ms": round(p95([i["latency_ms"] for i in itens]), 1),
        "taxa_resposta": round(len(respondidos) / max(len(itens), 1), 4),
        "citacao_em_respondidas": (
            round(sum(1 for i in respondidos if i["citacao_ok"]) / len(respondidos), 4)
            if respondidos
            else None
        ),
        "fonte_correta_em_respondidas": (
            round(sum(1 for i in respondidos if i["fonte_correta"]) / len(respondidos), 4)
            if respondidos
            else None
        ),
        "tokens_input_total": sum(i["tokens"]["input"] for i in itens),
        "tokens_output_total": sum(i["tokens"]["output"] for i in itens),
        "ragas": _opcional("RAGAS", _ragas_metricas, itens),
    }
    return {"metricas": metricas, "itens": itens}


def _salvar_bruto(itens: list[dict]) -> None:
    """Persiste a geracao assim que ela termina.

    Sao ~20 min de LLM local: nenhuma metrica opcional pode fazer isso ser perdido.
    """
    RESULTADOS.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (RESULTADOS / f"bruto_{stamp}_{_commit_hash()}.json").write_text(
        json.dumps(itens, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _salvar(resultado: dict) -> Path:
    """Grava dois arquivos: o completo (local) e o resumo de metricas (versionavel).

    O completo carrega `contexts` — o TEXTO dos chunks — e as respostas geradas a partir
    dele. Isso e material do curso e fica no `.gitignore`. O resumo tem so numeros, e e
    ele que alimenta o grafico de evolucao por commit exigido pela SPEC.
    """
    RESULTADOS.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    commit = _commit_hash()
    cabecalho = {"timestamp": stamp, "commit": commit, "curso": settings.curso_nome}
    # O resumo e VERSIONADO (excecao `!metricas_*.json` no .gitignore), entao ele nao
    # pode carregar `CURSO_NOME`: num corpus real esse campo e o nome da escola dona do
    # material, e a auditoria GOV-5 tirou esse nome do repo. O arquivo era regenerado a
    # cada rodada com o valor do .env, entao a limpeza de uma vez nao bastava. Para ler
    # o numero, o que importa e QUAL corpus foi medido -- nao como ele se chama.
    corpus = (
        "real (privado)"
        if settings.golden_set.name.endswith(".local.jsonl")
        else "publico (samples/)"
    )
    cabecalho_publico = {"timestamp": stamp, "commit": commit, "corpus": corpus}

    caminho = RESULTADOS / f"eval_{stamp}_{commit}.json"
    caminho.write_text(
        # allow_nan=False: `NaN` e extensao do Python, nao JSON valido -- `JSON.parse`,
        # `jq` e parsers estritos rejeitam. Estes arquivos sao o artefato versionado do
        # grafico de evolucao, entao e melhor estourar aqui do que gravar um resultado
        # que o consumidor nao consegue ler.
        json.dumps({**resultado, **cabecalho}, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )

    (RESULTADOS / f"metricas_{stamp}_{commit}.json").write_text(
        json.dumps(
            {
                **cabecalho_publico,
                "metricas": resultado["metricas"],
                "config": {
                    "llm_model": settings.llm_model,
                    "embedding_model": settings.embedding_model,
                    "score_threshold": settings.score_threshold,
                    "final_k": settings.final_k,
                    "retrieve_k": settings.retrieve_k,
                    "rerank_enabled": settings.rerank_enabled,
                    "bm25_rescue_min_idf": settings.bm25_rescue_min_idf,
                    "golden_set": settings.golden_set.name,
                },
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    return caminho


def main() -> int:
    if not settings.openai_api_key:
        print("erro: OPENAI_API_KEY ausente — o eval precisa do pipeline completo")
        return 2

    print(f"avaliando {len(carregar_golden_set())} itens de {GOLDEN_SET.name}...")
    resultado = run()
    caminho = _salvar(resultado)
    print(json.dumps(resultado["metricas"], ensure_ascii=False, indent=2))
    print(f"resultado salvo em {caminho}")

    if not settings.eval_strict:
        return 0
    m = resultado["metricas"]
    falhas = []
    if m["recusa_correta"] is not None and m["recusa_correta"] <= META_RECUSA_CORRETA:
        falhas.append(f"recusa_correta {m['recusa_correta']:.3f} <= {META_RECUSA_CORRETA}")
    if m["alucinacao"] is not None and m["alucinacao"] >= META_ALUCINACAO:
        falhas.append(f"alucinacao {m['alucinacao']:.3f} >= {META_ALUCINACAO}")
    if m["latency_p95_ms"] >= META_LATENCIA_P95_MS:
        falhas.append(f"latency_p95_ms {m['latency_p95_ms']} >= {META_LATENCIA_P95_MS}")
    if falhas:
        print("REPROVADO: " + "; ".join(falhas))
        return 1
    print("APROVADO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
