# GOV-1 — Pedido de autorização (rascunho)

Bloqueia o uso do corpus real, **não** o código. Decidir até o fim da semana 1 (SPEC seção 9).
E-mail basta; guarde a resposta.

A frase que faz um jurídico responder com clareza é a que diz que a API da OpenAI é um
serviço externo e que o conteúdo sai da infraestrutura da empresa. Omitir isso é o tipo de
coisa que estoura depois.

---

**Assunto:** Autorização para uso de material de curso em projeto pessoal de portfólio

Oi [nome],

Estou construindo um projeto pessoal de portfólio: um assistente de IA que responde dúvidas
de alunos usando exclusivamente o conteúdo do curso, sempre citando a aula de origem. Nasceu
de um problema que eu via na operação — as mesmas dúvidas voltando toda semana, com a
resposta já existindo no material.

Gostaria de pedir autorização para três coisas, e queria ser explícito em cada uma:

1. **Processar o material do curso** ([listar exatamente quais módulos/arquivos]) em um
   projeto pessoal, rodando na minha máquina.
2. **Enviar trechos desse material para a API da OpenAI.** A OpenAI é um serviço externo:
   na prática, trechos do conteúdo saem da infraestrutura da empresa e são processados por
   um terceiro. É o ponto que quero deixar claro antes de qualquer coisa.
3. **Publicar o código no GitHub e falar publicamente sobre o projeto** (LinkedIn, vídeo de
   demonstração). O **conteúdo do curso não seria publicado** em nenhuma hipótese: o
   repositório e a demo pública usam um corpus aberto e separado. O material de vocês ficaria
   só na minha máquina.

Sobre proteção de dados: as transcrições de aula ao vivo contêm nomes, e-mails e às vezes
dados de negócio de quem faz a pergunta. O projeto roda um passo de anonimização
(e-mail, telefone, CPF) antes de qualquer processamento.

Se a resposta for não em qualquer um dos três pontos, tudo bem — sigo com material
educacional aberto e nada muda no cronograma.

Obrigado,
Bruno

---

## Registro da decisão

| Campo | Valor |
|---|---|
| Enviado em | — |
| Para | — |
| Resposta em | — |
| Resultado | ⬜ autorizado · ⬜ negado · ⬜ parcial |
| Onde a resposta está guardada | — |

Se negado ou sem resposta até o fim da semana 1: trocar o corpus por material aberto
(MIT OpenCourseWare, documentação técnica, curso fictício) e manter a narrativa em
"o problema que eu via operando cursos online". Atualizar GOV-1 e GOV-3 na SPEC.
