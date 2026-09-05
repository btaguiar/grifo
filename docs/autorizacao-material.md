# GOV-1 — Pedido de autorização de uso do material

Bloqueia o uso do corpus real, **não** o código (SPEC seção 9). E-mail basta; guarde a
resposta.

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
| Enviado em | — |
| Para | — |
| Resposta em | — |
| Resultado (a) uso local | ⬜ autorizado · ⬜ negado |
| Resultado (b) provedor externo | ⬜ autorizado · ⬜ negado |
| Resultado (c) menção pública | ⬜ autorizado · ⬜ negado |
| Onde a resposta está guardada | — |

**Se (a) for negado ou não houver resposta:** apagar a coleção e `data/raw/`, e manter o
projeto sobre `samples/`, que é o que a demo e o CI já usam. A narrativa do portfolio não
depende do corpus real: ela é "o problema que eu via operando cursos online". O que se
perde são os números medidos sobre material de verdade, e a seção 3.1 do EVALUATION
passaria a ser histórica, não reproduzível.

**Enquanto não houver resposta:** vale o que está escrito no pedido. Nada de provedor
remoto com o corpus real, nada de mencionar a escola. As duas restrições estão
implementadas, não só combinadas: o `.env` aponta para modelo local, e a auditoria GOV-5
tirou os nomes do repositório.
