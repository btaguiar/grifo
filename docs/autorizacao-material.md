# GOV-1 — Pedido de autorização de uso do material

> **Resolvido em setembro de 2026: os três pedidos foram autorizados** — (a) uso local,
> (b) envio de trechos a provedor externo e (c) menção pública. O registro está no fim
> deste arquivo. O texto do pedido fica preservado abaixo como o que foi efetivamente
> enviado, no tempo verbal em que foi escrito.
>
> **Autorizado não é feito, e não é tudo.** Publicar o *conteúdo* do material nunca foi
> pedido nem concedido: ele continua fora do repositório, e continua sendo o `.gitignore`
> que garante isso. O repositório também segue sem nomear a escola — o (c) permite
> nomear, não obriga, e essa é uma escolha editorial separada.

Bloqueava o uso do corpus real, **não** o código (SPEC seção 9). E-mail bastou; a
resposta está guardada fora do repositório.

**Este arquivo é versionado no repositório público.** Por isso ele não nomeia a escola
nem os mentores: os campos entre colchetes são preenchidos na hora de enviar, fora daqui.
Ver a auditoria GOV-5 na SPEC seção 9.

**Leia antes de enviar.** O texto abaixo declara o que **já foi feito**, porque já foi.
O material foi processado, o código foi publicado, e as métricas saíram. Um pedido
escrito como se nada tivesse acontecido seria desmentido pelo primeiro `git log` que a
outra parte abrisse, e a data do repositório é pública. A força deste pedido está
exatamente em chegar com o trabalho já feito da forma mais conservadora possível:
localmente, sem publicar o conteúdo, sem identificar a escola. É isso que ele pede para
ratificar.

A frase que faz um jurídico responder com clareza é a que diz o que sai da máquina e o
que não sai. Omitir isso é o tipo de coisa que estoura depois.

---

**Assunto:** Autorização de uso de material de curso em projeto pessoal de portfólio

Oi [nome],

Construí um projeto pessoal de portfólio e queria acertar formalmente com vocês o uso do
material antes de seguir. Prefiro fazer isso por escrito, e prefiro fazer agora.

**O que é o projeto.** Um assistente que responde dúvidas de aluno usando exclusivamente
o conteúdo do curso, sempre citando a aula de origem, e que responde "não encontrei isso
no material" quando a resposta não está lá. Nasceu de um problema que eu via na operação:
as mesmas dúvidas voltando toda semana, com a resposta já existindo no material.

**O que eu já fiz, e como.** Indexei [N] transcrições de sessões de [nomear os módulos]
na minha máquina, para medir se a ideia funcionava. Três pontos sobre como:

1. **Nada do conteúdo saiu da minha máquina.** O modelo de linguagem e o cálculo dos
   embeddings rodaram localmente. Nenhum trecho do material foi enviado para OpenAI,
   Google, Anthropic ou qualquer outro serviço de terceiros. Isso foi uma decisão de
   projeto tomada justamente porque esta autorização ainda não existia.
2. **O material não está publicado em lugar nenhum.** O repositório é público, mas o
   conteúdo do curso nunca entrou nele. O que está lá roda sobre um corpus de exemplo
   separado, escrito do zero. O material de vocês existe só no meu computador.
3. **O repositório não identifica vocês.** Nem o nome da escola, nem os nomes dos
   mentores, nem os títulos das aulas aparecem em qualquer arquivo publicado. As
   referências são genéricas, do tipo "Módulo 1, Aula 2". Os resultados de qualidade que
   publiquei aparecem como medidos sobre "corpus real (privado)".

**Sobre dados pessoais.** As transcrições de sessão ao vivo contêm nomes de quem fala e,
às vezes, dados de negócio de quem faz a pergunta. A ingestão remove e-mail, telefone e
CPF antes de indexar, e aplica o mesmo passo à pergunta do aluno antes de gravá-la em
log. Nomes próprios **não** são removidos: eles fazem parte da fala. Como nada disso é
publicado nem enviado a terceiros, o material permanece restrito à minha máquina.

**O que peço.** Separei em três, do menos ao mais, e vocês podem autorizar só o primeiro:

- **(a) Ratificar o uso local.** Manter o material indexado na minha máquina, nas
  condições acima: nada publicado, nada enviado a terceiros, escola não identificada.
  É exatamente o que existe hoje.
- **(b) Autorizar o envio de trechos a um provedor de IA externo.** Ainda não fiz isso e
  não farei sem resposta. Na prática significa que trechos do conteúdo sairiam da
  infraestrutura de vocês e seriam processados por um terceiro. É o ponto que quero
  deixar explícito, porque é o que muda de natureza. Serve para medir a qualidade com
  modelos melhores que os que rodam no meu computador.
- **(c) Autorizar mencionar vocês publicamente.** Poder dizer que o projeto foi
  construído sobre material de vocês, num post ou numa entrevista. Continuaria sem
  publicar o conteúdo. Hoje o projeto é apresentado sem citar a origem.

Se a resposta for não em qualquer um dos três, tudo bem, e nada quebra: o (b) e o (c)
simplesmente não acontecem, e se o (a) também for não, eu apago o índice e o material da
minha máquina e sigo com o corpus de exemplo, que é o que o repositório público já usa.

Fico à disposição para mostrar o projeto rodando, ou para responder qualquer coisa sobre
como o material é tratado.

Obrigado,
Bruno Aguiar
[contato]

---

## Registro da decisão

| Campo | Valor |
|---|---|
| Enviado em | *(preencher: data de envio)* |
| Para | contato responsável na escola — não nomeado aqui, ver nota abaixo |
| Resposta em | *(preencher: data da resposta)* |
| Resultado (a) uso local | ✅ **autorizado** |
| Resultado (b) provedor externo | ✅ **autorizado** |
| Resultado (c) menção pública | ✅ **autorizado** |
| Onde a resposta está guardada | *(preencher: onde o e-mail de resposta está arquivado — fora do repositório)* |

Registrado em 2026-09-25. Os três campos entre parênteses dependem do e-mail em si e
ficam para quem tem a caixa de entrada aberta; os resultados, que são o que os outros
documentos citam, estão fechados.

**Por que "Para" continua genérico.** O (c) autoriza nomear a escola, e nomear passou a
ser uma escolha, não um risco. Enquanto essa escolha não for feita, este arquivo — que é
público — mantém o padrão dos outros: a origem do material não aparece. Trocar isso é
uma edição de um campo, no dia em que fizer sentido.

### O que a resposta mudou, e o que não mudou

**Mudou.** A rodada remota sobre o corpus real deixou de estar bloqueada. É a medição que
falta para fechar a lacuna declarada no EVALUATION: a alucinação do corpus real hoje não
se sustenta porque um 7B julgou a si mesmo, e o juiz forte (`gpt-4o`, κ = 0.905) só rodou
sobre corpus público. Com o (b) autorizado, o mesmo juiz pode julgar o corpus real. É
trabalho por fazer, não feito.

**Não mudou.** O conteúdo do material não vai para o repositório — isso não estava no
pedido. `data/raw/` e a coleção do corpus real continuam locais, o `.gitignore` continua
sendo a garantia, e `samples/` mais o corpus público em vídeo continuam sendo o que a
demo e o CI usam. A narrativa do portfolio também não muda: ela sempre foi "o problema
que eu via operando cursos online", e é isso que a torna independente de qualquer
autorização.

**O plano B, para registro.** Se (a) tivesse sido negado, o combinado era apagar a coleção
e `data/raw/` e seguir sobre `samples/`, com a seção 3.1 do EVALUATION passando a
histórica e não reproduzível. Não foi preciso.
