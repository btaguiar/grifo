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

import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from grifo.config import (  # noqa: E402
    REFUSAL_MESSAGE,
    SERIE_EVAL_LLM_MODEL,
    SERIE_FINAL_K,
    SERIE_GOLDEN_SET,
    SERIE_LLM_MODEL,
    SERIE_SCORE_THRESHOLD,
    custo_por_tokens,
    settings,
)
from grifo.generation.prompts import JUDGE_PROMPT  # noqa: E402

#: Configurável por GOLDEN_SET (.env ou variável de ambiente): o corpus real usa
#: eval/golden_set.local.jsonl, que não é versionado.
GOLDEN_SET = (REPO_ROOT / settings.golden_set).resolve()
RESULTADOS = Path(__file__).resolve().parent / "results"

_CITACAO_RE = re.compile(r"\[Módulo [^\],]+, Aula [^\],]+\]")

META_RECUSA_CORRETA = 0.95
META_ALUCINACAO = 0.02
META_LATENCIA_P95_MS = 3000
#: Calibrado da PRIMEIRA rodada medida com a métrica (contrato, 2026-09-06:
#: média 0.9545 em n=33), não a priori — com ~5pp de folga para o ruído conhecido:
#: paráfrase por sinônimo perde termo do gabarito sem errar conteúdo (gs-028 perde
#: "gasto"/"composto" para "paga"/"cíclico"). Recalibrar aqui ao redefinir o gabarito.
META_COBERTURA_MEDIA = 0.90


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


def normalizar_busca(texto: str) -> str:
    """Casefold sem acento: "Aquisição" casa com "aquisicao".

    O gabarito `expected_answer_contains` foi rotulado à mão e o modelo parafraseia —
    sem normalização, "número de clientes" não casa "Numero de clientes".
    """
    decomposto = unicodedata.normalize("NFD", texto)
    sem_acento = "".join(c for c in decomposto if unicodedata.category(c) != "Mn")
    return sem_acento.casefold()


def cobertura_conteudo(itens: list[dict]) -> dict | None:
    """Gabarito de resposta: fração dos termos de `expected_answer_contains` na resposta.

    Denominador = respondidas dentro do escopo COM gabarito (recusas ficam fora —
    quem não respondeu já aparece na taxa de resposta; contar aqui seria cobrar duas
    vezes o mesmo erro). Devolve a média por item e a proporção de itens com
    cobertura TOTAL (todos os termos presentes) — a segunda é mais dura e é ela que
    encontra a resposta "certa por cima": aula certa, conteúdo pela metade.
    """
    alvo = [
        i for i in itens if i["should_answer"] and i["found"] and i.get("expected_answer_contains")
    ]
    if not alvo:
        return None
    por_item: list[float] = []
    for i in alvo:
        resposta = normalizar_busca(i["answer"])
        termos = i["expected_answer_contains"]
        acertos = sum(1 for t in termos if normalizar_busca(t) in resposta)
        por_item.append(acertos / len(termos))
    return {
        "media": round(sum(por_item) / len(por_item), 4),
        "total_em_itens": round(sum(1 for c in por_item if c == 1.0) / len(por_item), 4),
        "n": len(por_item),
    }


#: O prompt do juiz vive em `src/grifo/generation/prompts/judge.txt` (Fase 5) e é
#: importado lá de cima — o SHA-256 dele acompanha o bloco `config` de cada rodada.
#: Calibrado contra eval/judge_calibration.jsonl; a versao anterior reprovava
#: parafrase fiel e inflou a taxa medida para 79,5% no corpus real.


def _llm_do_eval():
    """LLM do JUIZ -- `EVAL_LLM_MODEL`, caindo para `LLM_MODEL` quando nao definido.

    Separar os dois importa: com um so, o mesmo modelo responde e julga a propria
    resposta, o que infla faithfulness e mascara alucinacao. O default preserva o
    comportamento antigo para nao mudar rodada nenhuma em silencio.

    O api_key precisa ser passado explicitamente: pydantic-settings le o .env para o
    objeto Settings, NAO para os.environ, entao o ChatOpenAI nao o encontra sozinho.
    """
    from langchain_openai import ChatOpenAI
    from pydantic import SecretStr

    return ChatOpenAI(
        model=settings.eval_llm_model or settings.llm_model,
        temperature=0,
        api_key=SecretStr(settings.openai_api_key) if settings.openai_api_key else None,
        base_url=settings.openai_base_url or None,
    )


def _judge_alucinacao(itens: list[dict]) -> float | None:
    """LLM-as-judge: afirmação não sustentada pelos chunks recuperados (amostra calibrada à mão).

    Anota `alucinou` em cada item respondido — o veredito por item é o que permite
    reconciliar o juiz com o faithfulness do RAG (EVALUATION.md 5.8); a taxa sozinha
    esconde onde os dois discordam.
    """
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
        item["alucinou"] = veredito.startswith("SIM")
        alucinados += item["alucinou"]
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
    if not settings.ragas_enabled:
        return None
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
        from ragas.run_config import RunConfig
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
            run_config=RunConfig(
                timeout=settings.ragas_timeout, max_workers=settings.ragas_max_workers
            ),
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
        # Faithfulness POR ITEM (EVALUATION.md 5.8): a média esconde onde o juiz
        # próprio e o RAGAS discordam — a reconciliação item a item é o que
        # transforma duas métricas próximas em informação sobre cada uma. As linhas
        # do dataframe seguem a ordem dos itens respondidos que entraram no Dataset.
        respondidos = [i for i in itens if i["found"]]
        if "faithfulness" in df.columns and len(df) == len(respondidos):
            for item, valor in zip(respondidos, df["faithfulness"], strict=False):
                item["ragas_faithfulness"] = None if valor != valor else round(float(valor), 4)
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


def _juiz_de_registro() -> dict | None:
    """A calibração de registro (`calibracao_juiz.json`, gerada por `calibrar_juiz.py`).

    Toda rodada carrega a confiabilidade do juiz que a produziu: sem isto, um kappa
    medido num prompt antigo seria lido como se valesse para o atual. Se o hash do
    prompt calibrado divergir do `JUDGE_PROMPT` em uso, o bloco ganha a flag
    `prompt_divergente_do_calibrado` — recalibrar é a saída, não ignorar.
    """
    caminho = RESULTADOS / "calibracao_juiz.json"
    if not caminho.exists():
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    juiz = dados.get("juiz")
    if not juiz:
        return None
    if juiz.get("prompt_sha256") != hashlib.sha256(JUDGE_PROMPT.encode("utf-8")).hexdigest():
        juiz["prompt_divergente_do_calibrado"] = True
        juiz["modelo_calibrado"] = juiz.get("modelo")
        juiz["modelo"] = settings.eval_llm_model or settings.llm_model
        print("aviso: o JUDGE_PROMPT em uso diverge do calibrado — rode calibrar_juiz.py")
    return juiz


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
            # Re-tentativas de validação do contrato (Fase 2): quantas queries o
            # modelo devolveu saída que violou o Pydantic ao menos uma vez.
            "retries": resposta.get("retries", 0),
        }
        registro["fonte_correta"] = (
            fonte_bate(item["expected_source"], resposta["sources"])
            if item["should_answer"] and resposta["found"]
            else None
        )
        # A versão dura da mesma pergunta: a aula esperada foi CITADA pelo modelo,
        # não apenas recuperada. Só existe desde o contrato da Fase 2, que devolve
        # `citations` validadas — antes disso não havia como distinguir.
        registro["fonte_citada_correta"] = (
            fonte_bate(item["expected_source"], [s for s in resposta["sources"] if s.get("cited")])
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
        # Mesmo denominador da de cima, critério mais duro: a aula esperada aparece
        # entre as fontes que o modelo CITOU, não entre as que foram recuperadas. A
        # diferença entre as duas é o quanto o número anterior devia à generosidade
        # do critério, e é ela que interessa ler.
        "fonte_citada_correta_em_respondidas": (
            round(sum(1 for i in respondidos if i["fonte_citada_correta"]) / len(respondidos), 4)
            if respondidos
            else None
        ),
        # Gabarito de resposta (Fase 3): o expected_answer_contains era trabalho
        # rotulado sem consumidor — agora sustenta a métrica de cobertura.
        "cobertura_conteudo": cobertura_conteudo(itens),
        "tokens_input_total": sum(i["tokens"]["input"] for i in itens),
        "tokens_output_total": sum(i["tokens"]["output"] for i in itens),
        # Custo da GERAÇÃO pelos tokens medidos e preço público (Fase 4). None =
        # modelo fora da tabela de preços: não se publica custo estimado. Os tokens
        # do juiz/RAGAS não entram nos totais — ver EVALUATION.md seção 6.
        "custo_usd": custo_por_tokens(
            settings.llm_model,
            sum(i["tokens"]["input"] for i in itens),
            sum(i["tokens"]["output"] for i in itens),
        ),
        # Fase 2: proporção de queries que precisaram de >=1 re-tentativa de
        # validação do contrato. Denominador = TODAS as queries: recusa sem LLM
        # entra com 0 — é o custo total de retry do sistema por rodada.
        "retry_rate": round(sum(1 for i in itens if i.get("retries")) / max(len(itens), 1), 4),
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


def _eh_config_de_serie() -> bool:
    """A rodada atual roda na configuração canônica congelada da série?

    Qualquer peça fora do congelado (modelo, threshold, reranker, golden set,
    force_citation) faz a rodada sair com `serie: false` — números comparáveis entre
    si ou nada. É a mesma regra que impede as duas rodadas antigas de formarem série.
    """
    return (
        settings.llm_model == SERIE_LLM_MODEL
        and (settings.eval_llm_model or settings.llm_model) == SERIE_EVAL_LLM_MODEL
        and settings.score_threshold == SERIE_SCORE_THRESHOLD
        and settings.final_k == SERIE_FINAL_K
        and not settings.rerank_enabled
        and not settings.force_citation
        and settings.golden_set.name == SERIE_GOLDEN_SET
    )


def _hashes_dos_prompts() -> dict[str, str]:
    """SHA-256 dos prompts versionados — a assinatura que explica os números."""
    from grifo.generation.prompts import ANSWER_SYSTEM_PROMPT

    return {
        "answer_system": hashlib.sha256(ANSWER_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        "judge": hashlib.sha256(JUDGE_PROMPT.encode("utf-8")).hexdigest(),
    }


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
    cabecalho_publico = {
        "timestamp": stamp,
        "commit": commit,
        "corpus": corpus,
        #: A rodada entra na série temporal só na configuração canônica (Fase 4).
        #: False = comparável apenas consigo mesma — não some com as da série.
        "serie": _eh_config_de_serie(),
    }

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
                    # Quem JULGOU. Sem este campo a rodada nao e reproduzivel (NFR-8):
                    # o mesmo corpus julgado por modelos diferentes da numeros diferentes,
                    # e "modelo se auto-julgando" e um resultado diferente de "juiz
                    # independente" -- ver 5.7.
                    "eval_llm_model": settings.eval_llm_model or settings.llm_model,
                    "embedding_model": settings.embedding_model,
                    "score_threshold": settings.score_threshold,
                    "final_k": settings.final_k,
                    "retrieve_k": settings.retrieve_k,
                    "rerank_enabled": settings.rerank_enabled,
                    "bm25_rescue_min_idf": settings.bm25_rescue_min_idf,
                    "golden_set": settings.golden_set.name,
                    #: Se a citação foi pós-processada (`_ensure_citation`) nesta
                    #: rodada — sem isto, rodada A/B da Fase 2 é indistinguível.
                    "force_citation": settings.force_citation,
                    # Hashes dos prompts versionados (Fase 5): dois metricas com
                    # números diferentes sempre têm como ser explicados por
                    # diferença em config — inclusive a vírgula de prompt.
                    "prompt_sha256": _hashes_dos_prompts(),
                    # Confiabilidade do juiz que produziu esta rodada (plano de
                    # execução, Fase 1): kappa + matriz da calibração de registro.
                    # `null` = sem calibração de registro — a taxa de alucinação
                    # desta rodada sai sem lastro de confiabilidade.
                    "juiz": _opcional("calibração do juiz", _juiz_de_registro),
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
    cobertura = m.get("cobertura_conteudo")
    if cobertura is not None and cobertura["media"] < META_COBERTURA_MEDIA:
        falhas.append(f"cobertura_conteudo {cobertura['media']:.3f} < {META_COBERTURA_MEDIA}")
    if falhas:
        print("REPROVADO: " + "; ".join(falhas))
        return 1
    print("APROVADO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
