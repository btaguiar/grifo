# web/ — a demo pública

App Next que consome a API do Grifo. É a vitrine: quem abre precisa entender o produto
em poucos segundos, clicar numa sugestão e ver a resposta citando a aula com link para o
minuto do vídeo. A recusa tem peso visual próprio, porque é o que distingue este
assistente de um que responde qualquer coisa com confiança.

No ar em <https://grifo-one.vercel.app>, contra a API no Cloud Run.

```bash
npm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev
```

A API precisa liberar a origem do front, senão o navegador barra o `POST /ask` antes
de ele sair da máquina:

```bash
CORS_ORIGINS=http://localhost:3000 uvicorn grifo.api.main:app --port 8000
```

| Variável | Para que serve | Padrão |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | onde está a API | `http://127.0.0.1:8010` |
| `NEXT_PUBLIC_CURSO` | valor do campo `curso` no `POST /ask`, que filtra o corpus | `G4 Business (aulas públicas)` |

## Decisões

**Stack.** Next 16 com App Router, Tailwind v4, shadcn/ui e os componentes
[prompt-kit](https://prompt-kit.com) (`PromptInput`, `PromptSuggestion`). A página é
estática: o build gera HTML, e toda a conversa acontece no cliente contra a API. Isso
mantém a hospedagem trivial e o backend como única peça com estado.

**Um acento só.** Amarelo de marca-texto, porque grifar é marcar o trecho certo no
material. Ele aparece no traço do título, no botão de enviar, na aspa da fonte citada e
na borda da recusa. Nada mais na página usa cor.

**As sugestões saem do golden set** (`eval/golden_set_aulas_publicas.jsonl`), inclusive a
última, que não tem resposta no material. O visitante clica e vê a recusa sem precisar
inventar uma pergunta ruim. O que ele testa é exatamente o que a suíte de avaliação mede.

**Ícones do lucide**, não por preferência, mas porque é o que o prompt-kit importa: uma
família de ícones por projeto evita dois desenhos diferentes do mesmo símbolo.

**Tema segue o sistema.** O modo escuro do shadcn depende da classe `dark`, e um script
no `layout.tsx` a aplica antes da pintura. Sem ele a preferência do sistema era ignorada.

## Duas armadilhas que custaram tempo, registradas para não voltarem

**O `shadcn init` apontou `--font-sans` para ela mesma.** O Geist ficava órfão e a página
inteira caía na serifa padrão do navegador, o que passa despercebido numa captura rápida.

**O Next 16 bloqueia origem de desenvolvimento não autorizada.** Abrir por `127.0.0.1`
enquanto o servidor serve `localhost` derruba a hidratação: a página renderiza, aceita
digitação no textarea e não responde a clique nenhum. Use `localhost` em dev, ou declare
`allowedDevOrigins` no `next.config.ts`.
