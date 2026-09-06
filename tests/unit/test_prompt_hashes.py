"""O prompt só muda de propósito: o hash de referência trava a mudança acidental.

O histórico 0.43 → 0.795 → 0.045 de alucinação veio de trocar texto de prompt sem
deixar rastro. Desde a Fase 5 os prompts vivem em `.txt` versionados e este teste
compara o SHA-256 do arquivo contra a referência AQUI — se você editou o prompt e
veio parar neste erro: a mudança é legítima quando você decide que é. Atualize a
referência abaixo, rode `python eval/calibrar_juiz.py` (o kappa do juiz é do prompt
que o produziu) e mencione a troca no commit. O hash também vai no bloco `config`
de cada `metricas_*.json` — dois resultados com números diferentes sempre têm como
ser explicados por diferença em config.
"""

import hashlib

from grifo.generation.prompts import ANSWER_SYSTEM_PROMPT, JUDGE_PROMPT

#: Referência do prompt de resposta (answer_system.txt).
HASH_ANSWER_SYSTEM = "d211c605f0657713291bb24aae428f7c6553feb4d0705fda432ba22dc81698b2"
#: Referência do prompt do juiz (judge.txt).
HASH_JUDGE = "e50687b4d6efbc56592db038ff87657e4befedbd27b793cccc7e367fb0f61af6"

_INSTRUCAO = (
    "prompt mudou sem atualizar o hash de referência. Se a mudança é intencional: "
    "atualize a constante neste teste, rode `python eval/calibrar_juiz.py` e cite a "
    "troca no commit — número de prompt é decisão, não efeito colateral."
)


def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def test_hash_do_prompt_de_resposta():
    assert _sha256(ANSWER_SYSTEM_PROMPT) == HASH_ANSWER_SYSTEM, _INSTRUCAO


def test_hash_do_prompt_do_juiz():
    assert _sha256(JUDGE_PROMPT) == HASH_JUDGE, _INSTRUCAO


def test_run_eval_carrega_o_mesmo_prompt_do_teste():
    """Uma só fonte: o que o eval julga é o que este teste trava."""
    from eval.run_eval import JUDGE_PROMPT as JUDGE_NO_EVAL

    assert JUDGE_NO_EVAL is JUDGE_PROMPT
