# samples/ — corpus aberto, commitado

Este é o corpus **público** do projeto: o que o CI usa, o que a demo no Streamlit Cloud
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

## A preencher

Substituir o conteúdo de exemplo por material educacional aberto de verdade — MIT
OpenCourseWare, documentação técnica, ou um curso fictício escrito por você. Semana 4.
