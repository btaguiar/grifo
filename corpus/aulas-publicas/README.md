# corpus/aulas-publicas — conteúdo aberto, reconstruído a partir dos links

Aulas públicas do canal [G4 Business](https://www.youtube.com/@G4Business) no YouTube.
Serve para que **a avaliação deste projeto seja reproduzível por terceiros**: o corpus
real é privado (`data/raw/`, fora do git) e o de `samples/` é pequeno demais para que
as métricas signifiquem alguma coisa.

## O que é versionado, e o que não é

| Arquivo | No git? | Por quê |
|---|---|---|
| `fontes.json` | **sim** | o mapa aula → URL e autor; é o que torna o corpus reconstruível |
| `*.vtt` (transcrições) | **não** | conteúdo de terceiros. Link não é licença de redistribuição |

```bash
python scripts/baixar_aulas.py                 # legendas automáticas (json3)
python scripts/baixar_aulas.py --transcrever   # Whisper local nas aulas sem legenda
pip install -e ".[corpus]"                     # yt-dlp + faster-whisper
```

## As aulas e quem as dá

| Aula | Autor |
|---|---|
| 1 — Como vender mais e melhor | Alfredo Soares |
| 2 — Como crescer uma empresa | Bruno Nardon |
| 3 — Empreender do zero no Brasil | Guilherme Benchimol |
| 4 — Construir empresa do zero | Tallis Gomes |
| 5 — Marketing em 2026 | Fernando Miranda |
| 6 — IA nos negócios em 2026 | João Vitor Chaves |

O autor vem do `fontes.json` e entra na citação: `[Módulo 1, Aula 1 — Alfredo
Soares]`. Os nomes saem da descrição pública de cada vídeo.

## Duas armadilhas medidas, para não serem redescobertas

**A legenda automática vem em formato rolante.** Cada bloco repete as linhas do
anterior, e o `--convert-subs vtt` do yt-dlp preserva a repetição. Numa aula de 40min:
95.121 caracteres pelo VTT convertido contra **32.884** pelo `json3` — o triplo, de
texto duplicado, que entraria no índice sem erro nenhum aparecer. O script extrai do
`json3` e monta o VTT.

**Duas aulas não têm legenda nenhuma no YouTube** (`aula-05`, `aula-06`): são
transcritas localmente com `faster-whisper`. Erro de download de áudio (403, ou
"Requested format is not available" em todo player_client) costuma ser **yt-dlp
desatualizado**, não bloqueio real — foi o que aconteceu em 2026-09-24.

## Procedência

Vídeos abertos, no canal de quem produziu o material, e a citação devolve o aluno para
o vídeo original no minuto exato. O direito autoral continua de quem publicou; este
repositório guarda apenas links e métricas derivadas. A autorização formal de uso
(GOV-1, [docs/autorizacao-material.md](../../docs/autorizacao-material.md)) segue seu
curso em paralelo e vale para o corpus privado.
