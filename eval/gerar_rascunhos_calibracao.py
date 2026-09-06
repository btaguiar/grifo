"""Gera rascunhos de calibração para o juiz de alucinação (plano de execução, Fase 1).

    python eval/gerar_rascunhos_calibracao.py

Expande `eval/judge_calibration.jsonl` de 6 para ~99 casos na distribuição-alvo do
plano (~40% fiéis / ~30% paráfrase fiel agressiva / ~30% com fato novo injetado),
fabricados a partir das respostas REAIS da rodada pública de 2026-09-03
(eval_20260903T232356Z_0561163.json — corpus de `samples/`, commitado; o arquivo de
rodada é local por privacidade, mas os rascunhos só carregam texto do corpus público).

Todo caso novo nasce com `"rascunho": true`: o rótulo é proposta, não verdade. A
revisão humana é o trabalho que falta — conferir rótulo e texto, ajustar o que
precisar e apagar o campo `rascunho` para o caso entrar na conta do kappa.

As três famílias:

  fiel        resposta real da rodada, verbatim (alucina: false). Ao revisar,
              confrontar com o `ragas_faithfulness` da próxima rodada: item com
              faithfulness baixo é onde o rótulo merece desconfiança.

  paráfrase   reescrita agressiva — sinônimo, reordenação, tom de aula, contração —
              sem fato novo (alucina: false). É o eixo que a primeira versão do
              juiz reprova sem querer.

  injetado    resposta real + UM fato novo (número, data, nome, benchmark,
              recomendação) ausente do contexto (alucina: true). O script confere
              por código que o `marcador` do fato não aparece no contexto —
              injeção acidental é rótulo errado sem ninguém ver.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AVALIACAO = REPO_ROOT / "eval" / "results" / "eval_20260903T232356Z_0561163.json"
CALIBRACAO = REPO_ROOT / "eval" / "judge_calibration.jsonl"

# id do golden set -> resposta reescrita SEM fato novo (paráfrase fiel)
PARAFRASES: dict[str, str] = {
    "gs-001": "Pegue tudo o que você gastou para conquistar clientes — mídia, salário do pessoal comercial, ferramentas de venda — e divida pelos clientes que entraram no mesmo período. Cuidado com a pegadinha do só-anúncios: o número sai bonito demais e te leva a investir errado [Módulo 2, Aula 4].",
    "gs-007": "Gestão 4.0 é decidir com número na mesa, não com palpite. A transformação digital que prestava não começa no carrinho de compras de software: começa escolhendo quais decisões do dia a dia passam a andar com dados — a tecnologia entra por último. O curso organiza tudo em quatro movimentos que se repetem: Alinhar (conectar a meta ao que a equipe executa), Rodar (ciclos curtos, de preferência semanais), Corrigir (comparar com o esperado e ajustar sem drama) e Otimizar (tirar o gargalo antes de escalar). E o indicador precisa estar na frente de quem executa, no ritmo da execução: quem opera é quem gera o dado, e planilha que chega uma semana tarde atrasa a correção numa semana [Módulo 1, Aula 1].",
    "gs-008": "Porque a parte que importa não é a compra de software, é escolher quais decisões cotidianas passam a ser orientadas por dados. A tecnologia vem por último, não primeiro — gerir com dados em vez de opinião é o que destrava a mudança [Módulo 1, Aula 1].",
    "gs-009": "São quatro movimentos que se repetem em ciclo: primeiro você Alinha (liga a meta ao que a equipe dá conta de executar), depois Roda (em ciclos curtos — semanais, idealmente), então Corrige (checa o resultado contra o esperado e ajusta a rota sem drama) e por fim Otimiza (elimina o gargalo que sobrou antes de escalar). A sequência não é sugestão: acelerar um processo desalinhado só faz a empresa errar mais rápido [Módulo 1, Aula 1].",
    "gs-010": "Porque otimização acelera o que já existe — e se o que existe está desalinhado, você instala o erro em velocidade maior. Primeiro conecte a meta ao que a equipe executa; só depois vale tirar o gargalo. A ordem é o ponto [Módulo 1, Aula 1].",
    "gs-011": "Quem opera o processo — não o gestor. Quem executa é quem gera o dado, e se o número só chega ao gestor uma semana depois, a correção atrasa uma semana. Gestão 4.0 encurta essa distância: indicador visível para quem executa, no ritmo da execução [Módulo 1, Aula 1].",
    "gs-012": "ICP é a EMPRESA que melhor se encaixa no que você vende — setor, porte, momento, orçamento. Persona é a PESSOA que decide a compra dentro dessa empresa — dores, objetivos, objeções. Trocar um pelo outro faz o comercial conversar com a pessoa errada dentro da empresa certa (ou o inverso) [Módulo 1, Aula 2].",
    "gs-013": "Olhe para a empresa que melhor se encaixa no que você vende e descreva: setor, porte, momento, orçamento. E não misture com persona — a pessoa que decide a compra lá dentro, com dores, objetivos e objeções próprias. Confundir os dois dá conversa com a pessoa errada na empresa certa [Módulo 1, Aula 2].",
    "gs-015": "Quatro perguntas: quais clientes renovam e expandem sem esforço comercial? O que eles têm em comum (setor, porte, maturidade)? Quais dão prejuízo ou desgaste desproporcional? E que evento/momento dispara a necessidade do que você vende? As respostas viram critério objetivo — sem isso, 'todo mundo que puder pagar' não qualifica nada [Módulo 1, Aula 2].",
    "gs-017": "Além da mídia: salários do time comercial e as ferramentas usadas no processo de venda. Somar só anúncios dá um CAC artificialmente baixo — e decisão de investimento tomada em número bonito é decisão errada [Módulo 2, Aula 4].",
    "gs-018": "Porque o número sai artificialmente baixo. CAC é o custo TOTAL de aquisição — mídia, salários do comercial, ferramentas de venda — dividido pelos clientes do período. Cortar dessa conta tudo que não é anúncio não economiza: distorce, e investimento decidido em número distorcido é investimento errado [Módulo 2, Aula 4].",
    "gs-021": "O funil é o caminho do lead do primeiro contato até a compra, em três regiões — topo, meio e fundo — e cada uma pede conversa diferente. No topo o lead acabou de sentir o problema e está aprendendo o nome dele: conteúdo educativo (guias, comparativos, artigos); vender aqui assusta. No meio ele compara soluções, quer diferenças, preços e riscos: estudo de caso, demo, prova de resultado. No fundo já decidiu comprar e está escolhendo de quem: prazo, implementação e condições — responder rápido vale mais que argumentar. A métrica central é a conversão entre etapas, medida etapa por etapa [Módulo 2, Aula 5].",
    "gs-023": "Comparação de soluções: diferenças, preços, riscos. O material certo aqui é estudo de caso, demonstração e prova de resultado — o lead do meio quer subsídio para escolher, não aula [Módulo 2, Aula 5].",
    "gs-025": "Taxa de conversão entre etapas — quantos leads de cada etapa avançam para a seguinte. Meça por etapa, nunca só o total: funil bom não é o que mais entra, é o que menos vaza onde importa [Módulo 2, Aula 5].",
    "gs-026": "É a condição objetiva que move o lead para a etapa seguinte. Sem ela escrita, cada vendedor inventa o que é um 'lead qualificado' [Módulo 2, Aula 5].",
    "gs-027": "Conserte o vazamento primeiro. Aquisição com retenção fraca é encher balde furado: antes de acelerar a entrada, meça a saída — churn, frequência de uso, expansão de contrato. Retenção é o multiplicador que transforma aquisição medíocre em crescimento bom (e a boa em excelente) [Módulo 3, Aula 6].",
    "gs-028": "Funil é modelo de gasto: você paga para o lead entrar, e ele desce até comprar ou vazar — quando o orçamento para, o crescimento para. Growth loop é o modelo em que a saída de um ciclo alimenta a entrada do seguinte (cliente que usa indica outro; conteúdo que vende gera conteúdo novo) — crescimento composto em vez de comprado. Ninguém vive só de loop, mas toda empresa deveria saber qual é o seu [Módulo 3, Aula 6].",
    "gs-029": "Porque retenção é multiplicador: aquisição medíocre com retenção boa vira crescimento bom, e aquisição boa vira excelente. Acelerar a entrada com a saída furada (churn alto) é encher balde furado — meça churn, frequência de uso e expansão de contrato antes de pisar no acelerador de leads [Módulo 3, Aula 6].",
    "gs-030": "NPS, medido a cada ciclo: 'de 0 a 10, quanto você recomendaria?', aplicado depois de um momento real de uso. E o que importa não é o número isolado — é a tendência e o comentário que vem junto, onde aparece por que o promotor promove e o detrator detona [Módulo 3, Aula 6].",
    "gs-031": "A tendência, com o comentário junto. O número sozinho diz pouco; é no comentário que aparece o motivo do promotor promover e do detrator detonar [Módulo 3, Aula 6].",
    "gs-032": "Não — o material chama isso de 'a forma elegante de não crescer nunca'. Estratégia de crescimento é escolher conscientemente um motor (retenção, indicação, conteúdo, parceria) e ter a disciplina de medir se ele gira [Módulo 3, Aula 6].",
    "gs-033": "Três: por custo (margem sobre o custo — simples, mas ignora o quanto o cliente valoriza), por concorrência (segue a tabela do mercado — confortável, mas entrega sua margem ao concorrente mais desesperado) e por valor (ancora no resultado econômico que o produto gera para o cliente — a recomendada pelo curso) [Módulo 3, Aula 7].",
    "gs-034": "Porque margem sobre custo ignora o quanto o cliente valoriza o que você vende — preço que não conversa com o valor gerado. A recomendada é a de valor: ancorar a conversa no resultado econômico para o cliente [Módulo 3, Aula 7].",
    "gs-035": "Ele segue a tabela do mercado — confortável, mas você entrega sua margem nas mãos do concorrente mais desesperado [Módulo 3, Aula 7].",
    "gs-036": "É ancorar a conversa no resultado econômico que o produto gera para o cliente — precificar o que muda na vida de quem compra. É a estratégia que o curso recomenda; a técnica da âncora (mostrar primeiro a opção mais completa e cara) opera dentro dela [Módulo 3, Aula 7].",
    "gs-037": "Porque desconto sem contrapartida ensina o cliente a pedir desconto sempre [Módulo 3, Aula 7].",
    "gs-038": "Porque inflação existe e melhoria de produto também: preço parado é margem derretendo devagar. Mudança de preço é parte normal da gestão, não crise [Módulo 3, Aula 7].",
    "gs-041": "34 anos, gestora de operações de uma distribuidora de médio porte [Módulo 1, Aula 2].",
    "gs-045": "Abaixo de 1: razão LTV/CAC menor que 1 significa que cada cliente novo destrói valor [Módulo 2, Aula 4].",
    "gs-046": "Topo, meio e fundo — no topo o lead aprende o nome do problema, no meio compara soluções, no fundo já decidiu comprar e escolhe de quem [Módulo 2, Aula 5].",
}

# id do golden set -> (resposta real + fato novo, marcador do fato, o que foi injetado)
INJETADOS: dict[str, tuple[str, str, str]] = {
    "gs-011": (
        "Os indicadores devem estar visíveis para quem executa o processo, pois quem opera é quem gera o dado. Na prática, o material recomenda um painel com atualização diária e alertas automáticos quando o indicador sai da faixa [Módulo 1, Aula 1].",
        "alertas automáticos",
        "recomendação ausente do contexto (painel com atualização diária e alertas)",
    ),
    "gs-001": (
        "Para calcular o CAC, divida o custo total de aquisição pelo número de clientes conquistados no mesmo período, incluindo mídia, salários do time comercial e ferramentas. Um benchmark comum é manter o CAC abaixo de 10% do LTV por cliente [Módulo 2, Aula 4].",
        "10% do LTV",
        "benchmark numérico ausente do contexto",
    ),
    "gs-007": (
        "Gestão 4.0 é gerir a empresa decidindo com dados em vez de opinião, organizada em quatro movimentos que se repetem: Alinhar, Rodar, Corrigir e Otimizar. Segundo a aula, empresas que adotam esse modelo reduzem o ciclo de decisão em média 40% [Módulo 1, Aula 1].",
        "40%",
        "número de produtividade ausente do contexto",
    ),
    "gs-009": (
        "O ciclo de quatro movimentos funciona assim: Alinhar é conectar a meta ao que a equipe consegue executar; Rodar é executar em ciclos curtos, de preferência semanais; Corrigir é comparar o resultado com o esperado e ajustar a rota sem drama; Otimizar é eliminar o gargalo antes de escalar. O material recomenda que cada ciclo completo tenha duração de 30 dias [Módulo 1, Aula 1].",
        "30 dias",
        "duração de ciclo ausente do contexto",
    ),
    "gs-010": (
        "Otimizar um processo desalinhado é problema porque faz a empresa errar mais rápido. O material cita o caso de uma indústria que duplicou a capacidade produtiva com o processo desalinhado e triplicou o prejuízo [Módulo 1, Aula 1].",
        "triplicou o prejuízo",
        "caso/nome ausente do contexto",
    ),
    "gs-012": (
        "O ICP descreve a empresa cliente com o melhor encaixe com o que você vende; a persona descreve a pessoa que decide a compra dentro dessa empresa. O material recomenda revisar o ICP a cada seis meses [Módulo 1, Aula 2].",
        "seis meses",
        "recomendação temporal ausente do contexto",
    ),
    "gs-013": (
        "Para definir o perfil de cliente ideal, considere setor, porte, momento e orçamento da empresa que melhor se encaixa no que você vende. A aula sugere começar analisando os últimos 12 meses de faturamento por cliente [Módulo 1, Aula 2].",
        "12 meses",
        "método numérico ausente do contexto",
    ),
    "gs-015": (
        "Para qualificar o cliente ideal, faça perguntas como: quais clientes renovam e expandem contratos sem esforço comercial? O que têm em comum? Quais dão prejuízo desproporcional? Que evento dispara a necessidade? O material indica priorizar clientes com NPS acima de 50 nesse filtro [Módulo 1, Aula 2].",
        "NPS acima de 50",
        "critério numérico ausente do contexto",
    ),
    "gs-017": (
        "Além de anúncios, entram no CAC os salários do time comercial e as ferramentas usadas no processo de venda. Em média, esses itens representam 35% do CAC total nas empresas de tecnologia [Módulo 2, Aula 4].",
        "35%",
        "estatística setorial ausente do contexto",
    ),
    "gs-021": (
        "O funil de vendas representa o caminho do lead do primeiro contato até a compra, com três regiões: topo, meio e fundo. Um funil B2B típico converte cerca de 3% dos leads de topo em clientes [Módulo 2, Aula 5].",
        "3%",
        "taxa de conversão típica ausente do contexto",
    ),
    "gs-023": (
        "No meio do funil, o lead compara soluções: estudos de caso, demonstrações e provas de resultado funcionam melhor. A aula recomenda enviar um caso de sucesso por semana nessa etapa [Módulo 2, Aula 5].",
        "por semana",
        "cadência de conteúdo ausente do contexto",
    ),
    "gs-025": (
        "A métrica central do funil é a taxa de conversão entre etapas, medida por etapa e não só no total. O material considera saudável uma conversão mínima de 20% por etapa [Módulo 2, Aula 5].",
        "20%",
        "meta numérica ausente do contexto",
    ),
    "gs-026": (
        "Critério de saída é a condição objetiva que move o lead para a etapa seguinte do funil. O material dá o exemplo da empresa SoftSales, que aumentou a conversão em 15% depois de escrever critérios [Módulo 2, Aula 5].",
        "SoftSales",
        "empresa/caso ausente do contexto",
    ),
    "gs-027": (
        "Conserte o vazamento antes de aumentar a entrada: aquisição com retenção fraca é encher um balde furado. Meça churn, frequência de uso e expansão de contrato. O balde furado é a metafora usada pelo professor Philip Kotler [Módulo 3, Aula 6].",
        "Philip Kotler",
        "atribuição de autoria ausente do contexto",
    ),
    "gs-028": (
        "O funil é um modelo de gasto; o growth loop é um modelo em que a saída de um ciclo alimenta a entrada do seguinte. O case da Dropbox é o exemplo clássico citado na aula, com crescimento de 300% sem verba de mídia [Módulo 3, Aula 6].",
        "Dropbox",
        "case e número ausentes do contexto",
    ),
    "gs-029": (
        "Retenção antes de aquisição porque retenção é o multiplicador do crescimento. A aula menciona que subir a retenção em 5 pontos pode dobrar a receita em 18 meses [Módulo 3, Aula 6].",
        "18 meses",
        "projeção numérica ausente do contexto",
    ),
    "gs-030": (
        "Meça o NPS a cada ciclo, com a pergunta 'de 0 a 10, quanto você recomendaria?' aplicada depois de um momento real de uso. O NPS é calculado subtraindo os detratores dos promotores, e a/meta da aula é chegar a 70 [Módulo 3, Aula 6].",
        "chegar a 70",
        "meta numérica ausente do contexto",
    ),
    "gs-031": (
        "No NPS importa mais a tendência e o comentário do que o número isolado. O material recomenda acompanhar a tendência em janelas trimestrais [Módulo 3, Aula 6].",
        "trimestrais",
        "janela temporal ausente do contexto",
    ),
    "gs-032": (
        "Trocar de motor de crescimento todo mês é a forma elegante de não crescer nunca: estratégia é a escolha consciente de um motor e a disciplina de medir se ele gira. A aula sugere no mínimo dois trimestres com o mesmo motor antes de avaliar a troca [Módulo 3, Aula 6].",
        "dois trimestres",
        "prazo de avaliação ausente do contexto",
    ),
    "gs-033": (
        "As três estratégias clássicas de preço são: por custo, por concorrência e por valor, sendo a de valor a recomendada pelo curso. A aula cita a Netflix como exemplo de precificação por valor bem-sucedida [Módulo 3, Aula 7].",
        "Netflix",
        "empresa exemplo ausente do contexto",
    ),
    "gs-034": (
        "O preço por custo é limitado porque ignora o quanto o cliente valoriza o produto. O material alerta que essa estratégia perde em média 12% de margem por ano frente à precificação por valor [Módulo 3, Aula 7].",
        "12%",
        "comparativo numérico ausente do contexto",
    ),
    "gs-035": (
        "Precificar pela concorrência entrega sua margem nas mãos do concorrente mais desesperado. O material recomenda monitorar os preços dos três principais concorrentes toda segunda-feira [Módulo 3, Aula 7].",
        "toda segunda-feira",
        "prática de monitoramento ausente do contexto",
    ),
    "gs-036": (
        "Precificar por valor é ancorar a conversa no resultado econômico que o produto gera para o cliente — a estratégia recomendada. Dentro dela, use a âncora: apresente primeiro a opção mais completa e cara. A âncora foi descrita pela primeira vez em 1974 por Amos Tversky [Módulo 3, Aula 7].",
        "1974",
        "data histórica ausente do contexto",
    ),
    "gs-037": (
        "Dar desconto sem contrapartida é ruim porque ensina o cliente a pedir desconto sempre. Segundo a aula, cada desconto sem contrapartida reduz a chance de renovação em 8 pontos percentuais [Módulo 3, Aula 7].",
        "8 pontos",
        "estatística ausente do contexto",
    ),
    "gs-038": (
        "Nunca reajustar é erro porque inflação e melhoria de produto existem — preço parado é margem derretendo devagar. O material recomenda reajuste anual obrigatório por contrato [Módulo 3, Aula 7].",
        "reajuste anual obrigatório",
        "recomendação contratual ausente do contexto",
    ),
    "gs-042": (
        "A sigla usada para medir recomendação de clientes é NPS (Net Promoter Score), criada por Fred Reichheld em 2003 [Módulo 3, Aula 6].",
        "Fred Reichheld",
        "autoria/criação ausente do contexto",
    ),
    "gs-043": (
        "A técnica recomendada é a âncora: apresentar primeiro a opção mais completa e cara para que as demais pareçam razoáveis. A aula recomenda nunca aplicar a âncora em clientes de primeira compra [Módulo 3, Aula 7].",
        "primeira compra",
        "restrição ausente do contexto",
    ),
    "gs-044": (
        "ICP significa Ideal Customer Profile: a empresa cliente com o melhor encaixe no que você vende — setor, porte, momento e orçamento. O conceito ficou popular com o livro 'Predictable Revenue', de Aaron Ross [Módulo 1, Aula 2].",
        "Aaron Ross",
        "referência bibliográfica ausente do contexto",
    ),
    "gs-045": (
        "A razão LTV/CAC abaixo de 1 significa que cada cliente novo destrói valor. O material considera a razão ideal algo entre 3 e 5 [Módulo 2, Aula 4].",
        "entre 3 e 5",
        "faixa de referência ausente do contexto",
    ),
    "gs-046": (
        "As três regiões do funil são topo, meio e fundo. No topo o lead aprende o nome do problema, no meio compara soluções, no fundo decide de quem comprar. A aula atribui o modelo de funil a Elias St. Elmo Lewis [Módulo 2, Aula 5].",
        "Elias St. Elmo Lewis",
        "atribuição histórica ausente do contexto",
    ),
}


def main() -> int:
    if not AVALIACAO.exists():
        print(f"erro: {AVALIACAO} não existe — os rascunhos derivam da rodada pública local")
        return 2

    rodada = json.loads(AVALIACAO.read_text(encoding="utf-8"))
    base = {i["id"]: i for i in rodada["itens"] if i["found"]}
    faltando = [g for g in list(PARAFRASES) + list(INJETADOS) if g not in base]
    if faltando:
        print(f"erro: itens sem resposta na rodada: {faltando}")
        return 2

    # guarda de rótulo: o fato injetado precisa estar AUSENTE do contexto, ou o caso
    # seria 'paráfrase com número que já existe' rotulado como alucinação
    for gs, (_ans, marcador, _desc) in INJETADOS.items():
        if marcador.casefold() in base[gs]["context"].casefold():
            print(f"erro: marcador '{marcador}' de {gs} EXISTE no contexto — injeção inválida")
            return 3

    casos: list[dict] = [
        json.loads(linha)
        for linha in CALIBRACAO.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]
    proximo = max(int(c["id"].split("-")[1]) for c in casos) + 1

    def novo(gs: str, answer: str, alucina: bool, nota: str) -> dict:
        nonlocal proximo
        caso = {
            "id": f"jc-{proximo:03d}",
            "contexto": base[gs]["context"],
            "question": base[gs]["question"],
            "answer": answer,
            "alucina": alucina,
            "nota": nota,
            "rascunho": True,
        }
        proximo += 1
        return caso

    fiéis = 0
    for gs, item in base.items():
        casos.append(
            novo(
                gs,
                item["answer"],
                False,
                f"resposta real da rodada 2026-09-03 ({gs}), verbatim — ao revisar, "
                "confrontar com o faithfulness por item da próxima rodada",
            )
        )
        fiéis += 1

    for gs, resposta in PARAFRASES.items():
        casos.append(
            novo(
                gs,
                resposta,
                False,
                f"paráfrase fiel agressiva de {gs}: sinônimo, reordenação e tom "
                "colloquial sem fato novo — o eixo que o juiz não pode reprovar",
            )
        )

    for gs, (resposta, _marcador, desc) in INJETADOS.items():
        casos.append(
            novo(
                gs,
                resposta,
                True,
                f"fato novo injetado em {gs}: {desc} — verificado ausente do contexto",
            )
        )

    CALIBRACAO.write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in casos) + "\n",
        encoding="utf-8",
    )
    total = len(casos)
    confirmados = sum(1 for c in casos if not c.get("rascunho"))
    rot_sim = sum(1 for c in casos if c["alucina"])
    print(
        f"{total} casos ({confirmados} confirmados, {total - confirmados} rascunhos)\n"
        f"  fiéis (NÃO): {fiéis + 3}  paráfrases (NÃO): {len(PARAFRASES) + 1}  "
        f"injetados (SIM): {len(INJETADOS) + 3}\n"
        f"  distribuição SIM: {rot_sim}/{total} = {rot_sim / total:.0%}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
