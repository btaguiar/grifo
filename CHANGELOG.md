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

**O `pip install` matava a busca vetorial.** O `pyproject` permitia `qdrant-client<2` e
o compose fixava o servidor em 1.12.4; a combinação grava todos os vetores zerados, sem
erro nenhum. Ingestão limpa, `/ask` respondendo, e o retrieval semântico morto — só o
resgate léxico do ADR 001 ainda entregava chunks, porque é o único caminho desenhado
para ignorar o cosseno. Pins casados, e `upsert_chunks` agora lê de volta o que gravou e
falha alto se o vetor vier sem norma. Detalhes em [EVALUATION](EVALUATION.md) 5.6.

**Caminho do Docker validado de ponta a ponta.** Três correções vieram daí: o LLM local
era inalcançável de dentro do container (`127.0.0.1` é o próprio container —
`host.docker.internal` e `extra_hosts` resolvem), todo container novo rebaixava 458MB do
modelo de embedding (agora num volume), e o timeout de 15s do cliente Qdrant, hardcoded,
estourava no meio da ingestão de corpus grande.

**71 vulnerabilidades conhecidas, e o padrão por trás delas.** Um alerta do Dependabot
levou a uma auditoria completa: 71 avisos em 9 pacotes. O achado não foi nenhum CVE em
particular — foi que **todo upper bound do `pyproject` estava exatamente abaixo da
versão que corrige**. `pypdf<6` com a correção em 6.x, `langchain<0.4` com a correção em
1.3.9, `fastapi<0.116` prendendo o starlette, `sentence-transformers<4` prendendo o
transformers. Os tetos foram escritos para proteger de breaking changes e viraram uma
parede contra correção de segurança.

Analisadas uma a uma contra o que o projeto de fato executa, quase nenhuma era
alcançável: os avisos do langchain são em carregadores de prompt de arquivo e em
contagem de tokens de imagem, que este código não usa; os do transformers são em
`from_pretrained` de repositório hostil e em treino. A exceção real era o `pypdf`, que
parseia PDF — entrada não confiável — no caminho de ingestão.

Subidos todos assim mesmo, porque o teto não tinha justificativa técnica: zero
vulnerabilidades ao fim. O embedding foi conferido bit a bit antes e depois (cosseno
1,0000000000), então o índice existente continua válido. `pip-audit` entrou nas
dependências de desenvolvimento para isto ser reprodutível.

**Auditoria de governança antes de publicar (GOV-5).** Nenhum segredo em nenhum commit e
o material do curso nunca versionado — mas a *origem* do material vazava, e foi o que
motivou refazer o histórico.

## Setembro de 2026 — fechando o ciclo de avaliação

Sete frentes executadas contra um plano escrito ([docs/plano-execucao.md](docs/plano-execucao.md)).
O que segue está na ordem em que as coisas apareceram, e duas delas são pioras.

**O regex saiu do caminho de produção, e a citação parou de ser fabricada.** A saída do
LLM virou contrato Pydantic (`GrifoAnswer`) validado por instructor, com retry instruído:
violação de schema volta ao modelo como erro, em vez de o código consertar a saída por
fora. O par módulo/aula citado passa a ser validado contra os trechos efetivamente
recuperados — citar aula não consultada reprova o contrato. O `_ensure_citation`, que
anexava a citação à força em 9 de 44 respostas (20%), continua no código atrás de
`FORCE_CITATION=false` — mesmo padrão do reranker: mecanismo medido que ficou
explicitamente desligado. Rodadas A/B nas duas configurações: a citação é **1.00
espontânea, com zero re-validações**, e a rodada com a flag ligada não teve o que
consertar.

**E custou latência, que é o preço publicado.** O caminho estruturado troca chamada de
chat simples por tool calling, com o schema viajando em toda requisição: +55% de tokens
de entrada por pergunta (361 → 561) e p95 de 2,58s para 3,53s — acima da meta de 3s.
O NFR-1 volta a não atingir no corpus público. O ganho é a citação deixar de ser
artificial e a validação de fonte passar a existir; o custo é este, e está na tabela em
vez de numa nota de rodapé.

**Um campo do golden set estava rotulado à mão e sem consumidor nenhum.** O
`expected_answer_contains` existia nos dois golden sets desde o início e nenhuma métrica
o lia — o eval sabia dizer se a *aula* estava certa, nunca se a *resposta* estava. Virou
`cobertura_conteudo`, e os dois itens que ela reprova dizem exatamente o que ela existe
para dizer: um responde a definição sem os termos que a aula pede, o outro troca
"gasto"/"composto" por "paga"/"cíclico" — conteúdo certo, termo não. O limiar de 0.90
saiu da primeira rodada medida, não de um palpite anterior a ela.

**Duas rodadas versionadas não formam série.** Corpora, provedores e tamanhos diferentes:
dois pontos que não se ligam. Existe agora uma configuração canônica congelada, e a
rodada só grava `serie: true` se rodar exatamente nela — números comparáveis entre si ou
nada. Com isso vieram o gate de regressão contra a última rodada da série, o gráfico
derivado dos dados e o `custo_usd` calculado dos tokens medidos. O gate reprova hoje, no
p95, e foi deixado assim.

**Trocar uma vírgula de prompt movia os números sem deixar rastro.** O histórico
`0.43 → 0.795 → 0.045` de alucinação é esse efeito acontecendo três vezes. Os prompts
saíram do código para `.txt` versionados, o SHA-256 de cada um acompanha o bloco `config`
de toda rodada, e um teste trava o hash de referência: mudar prompt passa a exigir
atualizar o hash, o que torna a mudança decisão explícita em vez de efeito colateral.

**O juiz ganhou a máquina inteira antes de ganhar um número.** Matriz de confusão,
precisão, recall, taxa de falso positivo e Kappa de Cohen, com piso de 0.70 e registro
que acompanha cada rodada. O conjunto de calibração foi de 6 para 99 casos — mas 93
estavam marcados `"rascunho": true`, rótulo proposto e não revisado, e o
`calibrar_juiz.py` os exclui de propósito. Naquele ponto o kappa sairia sobre os mesmos 6
casos de sempre. Ficou declarado como falta em vez de contornado; o número veio depois,
mais abaixo.

**Medir os rótulos, e não só o juiz, mostrou que o kappa sairia inflado.** O
`calibrar_juiz.py` mede o juiz *contra* os rótulos; ninguém media os rótulos. A triagem
nova encontrou o problema: **61% dos casos positivos terminam numa frase que abre com
fórmula de atribuição** ("O material recomenda…") contra 2% dos negativos, e os positivos
são mais curtos — mediana de 214 chars contra 308. Duas pistas de *forma* que separam as
classes sem ler o contexto: um juiz pode acertar pela forma da fabricação, o kappa sobe, e
nenhuma métrica do relatório denuncia. A triagem também mostrou que os 99 casos cobrem só
33 contextos distintos, três famílias sobre cada um — kappa supõe itens independentes.
Ela reprovou, e corrigir isso passou a ser pré-condição da rotulagem, não um passo
depois dela.

**Uma reescrita em PowerShell deixou o README ilegível, e o commit seguinte não viu.** O
arquivo foi lido como Windows-1252 e regravado como UTF-8: "dúvidas" virou "dÃºvidas" em
301 pontos, bytes UTF-8 válidos e caracteres errados. O commit que veio depois removeu o
BOM e passou ao lado da causa. A assinatura estava nos próprios caracteres — `€`, `"`,
`‰`, `ƒ` são os bytes 0x80, 0x94, 0x89 e 0x83 do cp1252 —, e um `\x8d` solto denunciava
o decodificador que passa adiante os cinco bytes que aquela tabela não define. Ficou na
branch e não chegou ao `main`. É o mesmo modo de falha que este projeto vem colecionando:
tudo continua "funcionando", só que errado, e sem erro nenhum para avisar.

**A assinatura de superfície saiu da calibração.** Os 30 casos injetados foram
reescritos com o fato novo costurado no meio da resposta, sem fórmula de atribuição e no
comprimento dos negativos. O gap de fórmula caiu de 59pp para 2pp e a razão de tamanho
foi para 1.05; a triagem aprova. O gerador ficou idempotente — descarta rascunhos,
preserva o que já foi confirmado —, e a triagem continua no fluxo, porque fabricar em
série reintroduz a assinatura sem ninguém notar.

**O cliente HTTP era recriado a cada pergunta, e as citações eram descartadas.** O
cliente OpenAI passou a ser reaproveitado entre requisições; os hooks do instructor, não
— o `/ask` roda em threadpool, e estado compartilhado trocaria contagem de tokens e
retries entre requisições concorrentes. O efeito na latência ainda não foi medido. As
citações que o contrato validava eram jogadas fora antes da resposta: agora cada fonte
sai com `cited`, e o eval ganhou `fonte_citada_correta_em_respondidas`, que separa o que
o retrieval trouxe do que a resposta de fato citou.

**A regra de fronteira foi escrita antes da rotulagem, não durante.** Só conta como
alucinação fato novo ausente dos trechos — número, data, nome, benchmark, regra, prazo
ou recomendação. Consequência que os trechos sustentam não conta. Decidir isso caso a
caso durante a revisão faria o kappa medir a inconsistência de quem rotula.

**O kappa existe — e a primeira leitura dele estava errada.** Em vez de fingir revisão
humana de 93 rascunhos, `eval/confirmar_rotulos.py` confirma o rótulo que decorre da
construção do caso quando ele é mecanicamente verificável, e recusa o resto. Resultado:
91 confirmados por construção, 6 por leitura humana, 2 recusados pelo próprio invariante
e ainda em rascunho. Cada rótulo carrega a `procedencia`, e o kappa sai separado por ela.
O primeiro juiz medido foi o `qwen2.5-7b` local: κ 0.408, recall 0.364, zero acerto em
prazo e em recomendação. A leitura óbvia era reforçar essas categorias no prompt do juiz.
Antes de mexer, a mesma calibração rodou com `gpt-4o`, o juiz da série: **κ 0.905**,
recall 0.879, precisão 1.000 — mesmo prompt, mesmo SHA-256, mesmos 97 casos. O gargalo
era o modelo. A mudança de prompt não foi feita, porque consertaria o que não está
quebrado e trocaria número medido por hipótese; a decisão que ficou é não usar 7B como
juiz. Com isso a alucinação 0.00 das rodadas julgadas por `gpt-4o` fica sustentada pela
primeira vez, e a da linha de base sobre o corpus real — julgada pelo próprio 7B — passa
a ser lida como não sustentada. O commit que publicou o 0.408 estendeu essa
reinterpretação a uma rodada que o `gpt-4o` já tinha julgado; o seguinte corrigiu.
