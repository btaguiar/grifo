# samples/ — corpus aberto, commitado

Este é o corpus **público** do projeto: o que o CI usa, o que a demo
indexa, e o que quem clonar o repo consegue rodar. Material real de curso **nunca** vive aqui.

| Corpus | Onde vive | Uso |
|---|---|---|
| Real | `data/raw/`, só na máquina local, gitignored | Desenvolvimento, avaliação real, gravação do vídeo |
| Sanitizado / aberto | `samples/`, commitado | Demo pública, CI, quem clonar o repo |

O código recebe um path de diretório e não sabe a diferença (FR-10). Isso é requisito de
arquitetura, não gambiarra.

## Convenção de nomes

A estrutura de diretórios é o que alimenta os metadados `modulo` e `aula` do schema DC-1:

```
samples/curso-exemplo/
└── modulo-2-metricas/
    ├── aula-04-cac-e-ltv.md
    └── aula-05-funil.vtt
```

- `modulo-<n>-<slug>` → `"2 - Métricas"`
- `aula-<nn>-<slug>` → `"4 - CAC e LTV"`
- extensão define `fonte_tipo`: `.md` markdown · `.pdf` pdf · `.vtt`/`.srt` transcricao

## fontes.json — a URL de cada aula (opcional)

Quando o material está publicado em vídeo, um `fontes.json` na **raiz passada à
ingestão** liga cada arquivo à URL da sua aula, e a citação deixa de ser texto e vira
link para o minuto exato:

```json
{
  "curso-exemplo/modulo-2-metricas/aula-05-funil.vtt": {
    "url": "https://www.youtube.com/watch?v=AbC123",
    "autor": "Alfredo Soares"
  },
  "curso-exemplo/modulo-2-metricas/aula-04-cac-e-ltv.md": "https://youtu.be/DeF456"
}
```

Duas formas por chave: o objeto `{url, autor}` e a URL solta, que nasceu primeiro e
continua valendo. Com `autor`, a citação sai como `[Módulo 2, Aula 5 — Alfredo
Soares]` — num corpus de palestra cada aula é de uma pessoa, e de quem é a fala
importa tanto quanto de onde ela veio.

- A chave é o caminho do arquivo **relativo à raiz**, com barras normais.
- Arquivo fora do mapa fica sem URL, e isso não é erro: corpus misto é o caso comum.
- URL sem `http(s)` reprova a ingestão inteira. Citação que não abre é pior que
  citação ausente (ADR 003).
- A URL vira `?t=<segundos>` (ou `&t=`, se já houver query) usando o
  `timestamp_inicio` do trecho. É o mesmo cálculo na API e na UI: `grifo/citation.py`.

Legenda de vídeo público entra direto: baixe como `.vtt` e o loader de transcrição já
existente cuida do resto. **O que se versiona é o `fontes.json`, não a transcrição** —
quem clonar rebaixa a legenda a partir da URL. O direito autoral do material continua
de quem o publicou; link não é licença de redistribuição.

## A preencher

Substituir o conteúdo de exemplo por material educacional aberto de verdade — MIT
OpenCourseWare, documentação técnica, ou um curso fictício escrito por você. Semana 4.
