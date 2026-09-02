# Registro de desenvolvimento

O histórico deste repositório começa num commit único. O projeto nasceu com outro nome —
um que identificava a escola cujo material serviu de corpus real — e esse nome estava no
título do README, no pacote e espalhado por todos os commits anteriores. Publicá-los
significaria publicar a origem do material antes de a autorização de uso (GOV-1 na
[SPEC](SPEC.md)) ter voltado. O histórico foi refeito; o que ele contava fica aqui.

Não é changelog de releases. É a ordem em que as coisas foram descobertas, que num
projeto de RAG é a parte que ensina.

Um efeito colateral: os artefatos de avaliação em `eval/results/` carregam no nome e no
campo `commit` o hash da revisão em que a medição rodou, e esses hashes são da história
anterior — não resolvem neste repositório. As medições são as mesmas; só a numeração
das revisões mudou.

## Agosto de 2026 — v1 completa

**Implementação inicial.** Pipeline inteiro de uma vez: ingestão com chunking estrutural,
retriever híbrido, chain LCEL com citação obrigatória e recusa exata, API, UI e suíte de
testes. Os três ADRs da [ARCHITECTURE](ARCHITECTURE.md) datam daqui.

**Provedor de LLM configurável, e embeddings locais.** O LLM e os embeddings passam a
entrar por qualquer API compatível com OpenAI, escolhida só por variável de ambiente.
Foi o que permitiu medir o corpus real sem que um trecho sequer do material saísse da
máquina — e sem isso a linha de base teria de esperar a autorização.

**Segurança do material, e uma letra que valia 69x.** O `.gitignore` passou a cobrir os
resultados brutos da avaliação, que carregam o texto dos trechos recuperados. Na mesma
passada: no Windows, `localhost` resolve `::1` antes de `127.0.0.1` e cada requisição ao
Qdrant pagava ~200ms, que o cliente amplificava para ~2s por busca. Trocar o host tirou
o retrieval do caminho crítico — de ~2,07s para ~0,03s na query quente.

**O `/ask` nunca tinha funcionado.** `RunnableLambda` invoca a função com um argumento
só, e o passo de retrieval tinha assinatura de dois: todo o caminho de produção morria
com `TypeError`, enquanto os testes unitários passavam porque injetavam o retriever. No
mesmo commit: quando o próprio LLM recusava, a chain anexava uma citação à força e
devolvia `found: true` — recusa virando citação fabricada, exatamente o que o ADR 002
existe para impedir.

**O BM25 não resgatava, só reordenava.** O maior achado do projeto. A implementação
intersectava os rankings: só entrava no resultado o chunk que a busca vetorial já tinha
trazido. O BM25 promovia a ordem e nunca recuperava nada — o que anula a razão de
existir do ADR 001. Medido no corpus real, uma pergunta pelo nome exato de uma
ferramenta citada 8 vezes numa aula devolvia **zero** chunks, porque o cosseno daquele
trecho contra a pergunta é 0,026: ruído. Nenhum threshold o admitiria; quem tinha de
admitir era a evidência léxica. O critério de resgate não pode ser IDF puro (raridade
não é pertencimento ao domínio) nem frequência — é a concentração da ocorrência numa
aula. Detalhes e ablação em [EVALUATION](EVALUATION.md) 4.4.

**A suíte de avaliação media a coisa errada.** E, pior, perdia a rodada cara inteira
quando falhava no fim — depois de já ter gasto os tokens.

**Primeira linha de base sobre o corpus real.** 64 perguntas, 20% fora do escopo.
Recusa correta 1.00, alucinação 0.00 verificada à mão, e a latência falhando a meta.

## Setembro de 2026 — preparação para o portfolio

**Calibração por medição, contra o plano.** Três parâmetros vieram de um documento de
planejamento e os três estavam errados. O threshold em 0,35 deixava passar 10 de 11
perguntas fora do escopo; em 0,45 a recusa sobe sem perder cobertura. O reranker
`ms-marco-MiniLM` é treinado em inglês e **piorava** a ordem em português, custando
613ms — desligado por medição, não por prazo. E o BM25, que o plano mandava cortar
primeiro sob pressão, provou valer 9 pontos de acerto de fonte sozinho.

**Renomeação para Grifo.** Grifar é marcar o trecho certo no material.

**O cache do BM25 não invalidava, e a API não aquecia nada.** Dois problemas no mesmo
cache, e o primeiro não era de latência: o índice léxico é um snapshot tirado na
primeira query, e `/ingest` não o descartava — a busca vetorial enxergava o material
novo e o BM25 não, deixando o resgate cego justamente para o conteúdo mais recente, sem
erro nenhum. O segundo é que a primeira pergunta de cada processo custava ~10s, paga
pelo primeiro aluno depois de cada deploy.

**O default do `QDRANT_URL` ainda era `localhost`.** A correção de 69x tinha entrado no
`.env` e não no código: quem clonasse sem definir a variável pegava a rota lenta de volta.

**Auditoria de governança antes de publicar (GOV-5).** Nenhum segredo em nenhum commit e
o material do curso nunca versionado — mas a *origem* do material vazava, e foi o que
motivou refazer o histórico.
