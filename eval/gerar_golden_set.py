"""Gera um RASCUNHO de golden set a partir do corpus real (DC-3).

    python eval/gerar_golden_set.py --corpus corpus/aulas-publicas --curso "..."

Por que a partir do corpus, e não da cabeça de quem escreve: neste corpus de palestra
as perguntas "óbvias" de um curso de gestão ("como precificar?", "como contratar?")
são recusadas — o material fala de mentalidade e histórias, não de procedimento. Um
golden set escrito sem olhar o conteúdo mede a distância entre o que a gente imagina e
o que foi dito, não a qualidade do sistema.

Cada item nasce com `"rascunho": true`, num arquivo `.rascunho.jsonl` SEPARADO: o
`run_eval.py` nunca o lê por acidente. Promover é trabalho humano — conferir a
pergunta, conferir a aula esperada, apagar o campo e mover para o arquivo oficial.

Duas verificações mecânicas antes de gravar, na mesma linha do `confirmar_rotulos.py`:

- item dentro do escopo: cada expressão de `expected_answer_contains` precisa aparecer
  LITERALMENTE no trecho que a originou. Termo inventado vira gabarito inventado.
- item fora do escopo: o termo-chave NÃO pode aparecer em nenhum chunk do corpus.
  "Fora do escopo" que na verdade está no material ensina o sistema a recusar certo
  pelo motivo errado. Já pegou uma: a pergunta sobre cachorro, que alguém cita.

Dois passes. O geral sorteia trechos de todas as aulas; o factual sorteia só entre os
que têm número, porque a fatia factual do DC-3 existe para testar o BM25 e a primeira
rodada saiu 49 conceituais contra 5 factuais — palestra tem pouco dado duro, e ele
precisa ser procurado onde está.

O que este script NÃO faz: filtrar perguntas pelo que o pipeline já acerta. Rodar o
retrieval e descartar o que ele não encontra produziria um golden set que mede o
próprio pipeline — fonte@5 alta por construção. A primeira rodada é a medição, não o
critério de seleção.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import unicodedata
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from pydantic import BaseModel, Field  # noqa: E402

from grifo.config import settings  # noqa: E402
from grifo.ingest.chunker import chunk_documents  # noqa: E402
from grifo.ingest.loaders import load_directory  # noqa: E402

PROMPT = (Path(__file__).parent / "prompts" / "golden_set.txt").read_text(encoding="utf-8")

#: Trecho curto demais é saudação ou fala cortada: não sustenta pergunta.
MIN_CHARS_DO_TRECHO = 500
#: Alvo do DC-3: 20% fora do escopo.
ALVO_FORA = 12

#: Acrescentado ao prompt quando o trecho tem dado duro. Procurar a pergunta factual
#: onde o dado está é diferente de forçar o rótulo: o modelo continua livre para dizer
#: que o número é irrelevante, e nesse caso o trecho é descartado.
REFORCO_FACTUAL = (
    "ATENÇÃO: este trecho contém número, sigla ou nome próprio. Se algum deles "
    "sustentar uma pergunta de resposta objetiva, escreva essa pergunta e marque "
    "`categoria: factual`. Se o dado for irrelevante ou solto, siga a regra 5.\n\n"
)

#: Perguntas fora do escopo. Metade é VIZINHA do domínio (negócios, mas ausente do
#: material) — é o caso difícil, e o único que distingue recusa por ausência de recusa
#: por assunto estranho. `termo` é o que a verificação exige ausente do corpus.
FORA_DE_ESCOPO = [
    ("Qual a alíquota do Simples Nacional para serviços?", "simples nacional"),
    ("Como faço para registrar uma marca no INPI?", "inpi"),
    ("Qual o prazo de entrega da declaração do imposto de renda?", "imposto de renda"),
    ("Como calcular férias proporcionais de um funcionário CLT?", "férias proporcionais"),
    ("Quanto custa abrir uma holding patrimonial?", "holding"),
    ("Como declarar criptomoedas na receita federal?", "criptomoeda"),
    ("Qual a receita do bolo de cenoura?", "bolo de cenoura"),
    ("Me explica a teoria das cordas", "teoria das cordas"),
    ("Quem ganhou a Copa do Mundo de 2022?", "copa do mundo"),
    ("Qual a melhor raça de cachorro para apartamento?", "cachorro"),
    ("Como configurar um roteador wifi mesh?", "roteador"),
    ("Qual o melhor destino de férias em julho?", "destino de férias"),
    ("Como tratar uma dor de dente em casa?", "dor de dente"),
    ("Qual a diferença entre vinho tinto e branco?", "vinho tinto"),
    ("Qual o melhor horário para regar plantas?", "regar plantas"),
]


class PerguntaGerada(BaseModel):
    pular: bool = Field(default=False, description="trecho sem conteúdo para uma pergunta")
    question: str = ""
    #: Quem classifica é quem escreveu a pergunta. A primeira versão atribuía a
    #: categoria por rodízio na ordem da amostra, o que rotulou de "factual" pergunta
    #: conceitual — e a fatia factual existe para testar o BM25.
    categoria: Literal["conceitual", "factual"] = "conceitual"
    expected_answer_contains: list[str] = Field(default_factory=list)


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.lower())
    return " ".join("".join(c for c in sem_acento if not unicodedata.combining(c)).split())


def termos_ausentes(termos: list[str], trecho: str) -> list[str]:
    """Quais expressões do gabarito NÃO estão literalmente no trecho."""
    alvo = normalizar(trecho)
    return [t for t in termos if normalizar(t) not in alvo]


def aparece_no_corpus(termo: str, chunks: list[dict]) -> bool:
    alvo = normalizar(termo)
    return any(alvo in normalizar(c["text"]) for c in chunks)


def numero_de(rotulo: str) -> str:
    """De "2 - Metricas" para "2": o DC-3 guarda o número, não o título."""
    m = re.match(r"\s*(\d+)", rotulo)
    return m.group(1) if m else rotulo


def tem_dado_duro(texto: str) -> bool:
    """Número, percentual ou valor no trecho — onde mora pergunta factual."""
    return bool(re.search(r"\d+\s*(?:%|mil|milh|bilh|reais)|R\$\s*\d+|\b\d{2,}\b", texto))


def parecidas(pergunta: str, aceitas: list[str], limiar: float = 0.6) -> bool:
    """Perguntas quase iguais inflam o n sem acrescentar medição.

    Dois chunks vizinhos falam do mesmo assunto e rendem a mesma pergunta com outras
    palavras. Não é item novo: é o mesmo contado duas vezes, e a calibração do juiz já
    ensinou o preço de ignorar correlação entre itens (EVALUATION.md 7).
    """
    nova = set(normalizar(pergunta).split())
    for anterior in aceitas:
        velha = set(normalizar(anterior).split())
        uniao = nova | velha
        if uniao and len(nova & velha) / len(uniao) >= limiar:
            return True
    return False


def amostrar(chunks: list[dict], quantos: int, semente: int) -> list[dict]:
    """Amostra espalhada por aula: cobertura, não concentração numa aula só."""
    por_aula: dict[str, list[dict]] = {}
    for c in chunks:
        if len(c["text"]) >= MIN_CHARS_DO_TRECHO:
            por_aula.setdefault(c["metadata"]["aula"], []).append(c)
    rng = random.Random(semente)
    escolhidos: list[dict] = []
    aulas = sorted(por_aula)
    for i, aula in enumerate(aulas):
        cota = quantos // len(aulas) + (1 if i < quantos % len(aulas) else 0)
        candidatos = por_aula[aula]
        # Descarta as pontas: abertura e encerramento rendem pergunta sobre aplauso.
        margem = max(1, len(candidatos) // 10)
        miolo = candidatos[margem:-margem] or candidatos
        escolhidos += rng.sample(miolo, min(cota, len(miolo)))
    return escolhidos


def _structured():
    """Cliente instructor com o modelo do EVAL, não o que responde ao aluno."""
    import instructor
    from openai import OpenAI

    modo = {"tools": instructor.Mode.TOOLS, "json_schema": instructor.Mode.JSON_SCHEMA}
    cliente = instructor.from_openai(
        OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url or None),
        mode=modo[settings.llm_structured_mode],
    )
    modelo = settings.eval_llm_model or settings.llm_model

    def chamar(prompt: str) -> PerguntaGerada:
        return cliente.chat.completions.create(
            model=modelo,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
            response_model=PerguntaGerada,
            max_retries=2,
        )

    return chamar, modelo


def item_no_escopo(numero: int, pergunta: PerguntaGerada, trecho: dict, categoria: str) -> dict:
    m = trecho["metadata"]
    return {
        "id": f"ap-{numero:03d}",
        "question": pergunta.question.strip(),
        "expected_source": {"modulo": numero_de(m["modulo"]), "aula": numero_de(m["aula"])},
        "expected_answer_contains": pergunta.expected_answer_contains,
        "should_answer": True,
        "categoria": categoria,
        "rascunho": True,
        "origem": {"chunk": trecho["id"], "timestamp": m["timestamp_inicio"]},
    }


def _gerar_item(
    trecho: dict, reforco: str, alvo: str, itens: list[dict], notas: dict, structured
) -> None:
    """Um trecho vira no máximo um item; toda saída fica registrada em `notas`."""
    try:
        gerada = structured(
            PROMPT.format(reforco=reforco, aula=trecho["metadata"]["aula"], trecho=trecho["text"])
        )
    except Exception as exc:
        notas["descartados"].append(f"{trecho['id']}: erro do provedor ({type(exc).__name__})")
        return
    if gerada.pular or not gerada.question.strip():
        notas["pulados"] += 1
        return
    if alvo == "factual" and gerada.categoria != "factual":
        # O trecho tem número, mas o modelo não achou pergunta objetiva nele. Aceitar
        # a conceitual aqui desequilibra o alvo do DC-3 sem testar BM25 nenhum.
        notas["sem_pergunta_factual"] += 1
        return
    fora = termos_ausentes(gerada.expected_answer_contains, trecho["text"])
    if fora or not gerada.expected_answer_contains:
        notas["descartados"].append(f"{trecho['id']}: gabarito fora do trecho {fora or '(vazio)'}")
        return
    if parecidas(gerada.question, [i["question"] for i in itens]):
        notas["descartados"].append(f"{trecho['id']}: pergunta quase igual a uma já aceita")
        return
    itens.append(item_no_escopo(len(itens) + 1, gerada, trecho, gerada.categoria))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Rascunho de golden set a partir do corpus")
    p.add_argument("--corpus", type=Path, default=Path("corpus/aulas-publicas"))
    p.add_argument("--curso", default=settings.curso_nome)
    p.add_argument(
        "--saida", type=Path, default=Path("eval/golden_set_aulas_publicas.rascunho.jsonl")
    )
    p.add_argument("--semente", type=int, default=20260924)
    p.add_argument(
        "--amostra",
        type=int,
        default=110,
        help="trechos sorteados no passe geral; rende bem menos itens, porque o modelo "
        "pula transcrição sem substância e a verificação descarta o resto",
    )
    p.add_argument(
        "--amostra-factual",
        type=int,
        default=60,
        help="trechos COM dado duro sorteados no segundo passe (fatia factual do DC-3)",
    )
    args = p.parse_args(argv)

    docs = load_directory(args.corpus, curso=args.curso)
    chunks = chunk_documents(docs, settings.chunk_size, settings.chunk_overlap)
    print(f"corpus: {len(chunks)} chunks em {len({c['metadata']['aula'] for c in chunks})} aulas")

    structured, modelo = _structured()
    duros = [c for c in chunks if tem_dado_duro(c["text"])]
    print(f"modelo: {modelo} | trechos com dado duro: {len(duros)} de {len(chunks)}")

    itens: list[dict] = []
    notas: dict = {"descartados": [], "pulados": 0, "sem_pergunta_factual": 0}
    passes = [
        ("", amostrar(chunks, args.amostra, args.semente)),
        ("factual", amostrar(duros, args.amostra_factual, args.semente + 1)),
    ]
    vistos: set[str] = set()
    for alvo, amostra in passes:
        reforco = REFORCO_FACTUAL if alvo == "factual" else ""
        for trecho in amostra:
            if trecho["id"] in vistos:
                continue
            vistos.add(trecho["id"])
            _gerar_item(trecho, reforco, alvo, itens, notas, structured)

    for pergunta, termo in FORA_DE_ESCOPO:
        if sum(1 for i in itens if not i["should_answer"]) >= ALVO_FORA:
            break
        if aparece_no_corpus(termo, chunks):
            notas["descartados"].append(f"fora-de-escopo {termo!r}: APARECE no corpus")
            continue
        itens.append(
            {
                "id": f"ap-{len(itens) + 1:03d}",
                "question": pergunta,
                "expected_source": None,
                "should_answer": False,
                "categoria": "fora-de-escopo",
                "rascunho": True,
            }
        )

    linhas = [json.dumps(i, ensure_ascii=False) for i in itens]
    args.saida.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    dentro = [i for i in itens if i["should_answer"]]
    factuais = sum(1 for i in dentro if i["categoria"] == "factual")
    aulas = len({i["expected_source"]["aula"] for i in dentro})
    print(f"\n{args.saida}: {len(itens)} itens")
    print(f"  no escopo: {len(dentro)} ({len(dentro) - factuais} conceituais, {factuais} factuais)")
    print(f"  fora do escopo: {len(itens) - len(dentro)} | aulas cobertas: {aulas}")
    print(f"prompt sha256: {hashlib.sha256(PROMPT.encode()).hexdigest()[:16]}")
    print(f"trechos sem conteúdo (o modelo pulou): {notas['pulados']}")
    print(f"trechos com número sem pergunta factual: {notas['sem_pergunta_factual']}")
    if notas["descartados"]:
        print(f"descartados na verificação: {len(notas['descartados'])}")
        for d in notas["descartados"][:8]:
            print(f"   {d}")
    print("\nTodos com rascunho: true. Revise antes de mover para o golden set oficial.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
