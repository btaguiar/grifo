"""Monta o corpus de vídeo a partir do `fontes.json`: link -> transcrição local.

O que se versiona é o MAPA de links; a transcrição é derivada e fica fora do git
(.gitignore). Quem clonar roda este script e chega ao mesmo corpus — é o que torna a
avaliação reproduzível sem redistribuir material de terceiros.

    python scripts/baixar_aulas.py                    # legendas das aulas que têm
    python scripts/baixar_aulas.py --transcrever      # e transcreve as que não têm

**A legenda automática do YouTube vem em formato rolante**: cada bloco repete as linhas
do anterior, e o `--convert-subs vtt` preserva isso. Medido em 2026-09-24 numa aula de
40min: 95.121 caracteres pelo VTT convertido contra 32.884 pelo `json3` — o triplo, de
texto repetido, que iria para o índice sem nenhum erro aparecer. Por isso a extração
usa `json3` e monta o VTT aqui.

Requer `yt-dlp` no PATH; `--transcrever` requer `faster-whisper` e `ffmpeg`
(extra `corpus` do pyproject).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ_PADRAO = Path("corpus/aulas-publicas")
#: Um cue por frase curta agrupada: o chunker junta em janelas maiores depois, e cue
#: por palavra (o que o json3 entrega) deixaria o VTT ilegível para quem for conferir.
MAX_CHARS_POR_CUE = 300
#: Duração assumida para o último cue, que não tem um próximo para delimitá-lo.
CAUDA_SEGUNDOS = 5


def id_do_video(url: str) -> str:
    """`watch?v=ID`, `youtu.be/ID` ou `shorts/ID` -> ID."""
    p = urlparse(url)
    if p.hostname and p.hostname.endswith("youtu.be"):
        return p.path.lstrip("/").split("/")[0]
    v = parse_qs(p.query).get("v")
    if v:
        return v[0]
    partes = [x for x in p.path.split("/") if x]
    if partes and partes[0] in ("shorts", "embed", "live"):
        return partes[1] if len(partes) > 1 else ""
    raise ValueError(f"não consegui extrair o id do vídeo: {url}")


def hhmmss(ms: int) -> str:
    total = max(0, ms) // 1000
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}.000"


def agrupar_eventos(
    eventos: list[dict], max_chars: int = MAX_CHARS_POR_CUE
) -> list[tuple[int, str]]:
    """Eventos do json3 -> [(início em ms, texto)], agrupados em cues legíveis.

    O json3 entrega uma palavra (ou poucas) por evento, com `tStartMs`. Cada grupo
    guarda o início do PRIMEIRO evento: é esse valor que vira o `?t=` do link, e
    apontar para o começo do trecho é o comportamento certo.
    """
    cues: list[tuple[int, str]] = []
    inicio: int | None = None
    partes: list[str] = []
    for ev in eventos:
        texto = "".join(s.get("utf8", "") for s in ev.get("segs") or [])
        if not texto.strip():
            continue
        if inicio is None:
            inicio = int(ev.get("tStartMs", 0))
        partes.append(texto.strip())
        if sum(len(p) + 1 for p in partes) >= max_chars:
            cues.append((inicio, " ".join(partes)))
            inicio, partes = None, []
    if partes and inicio is not None:
        cues.append((inicio, " ".join(partes)))
    return [(ms, " ".join(t.split())) for ms, t in cues]


def montar_vtt(cues: list[tuple[int, str]]) -> str:
    """[(ms, texto)] -> WebVTT. O fim de um cue é o início do próximo (FR-33)."""
    linhas = ["WEBVTT", ""]
    for i, (ms, texto) in enumerate(cues):
        fim = cues[i + 1][0] if i + 1 < len(cues) else ms + CAUDA_SEGUNDOS * 1000
        linhas += [f"{hhmmss(ms)} --> {hhmmss(fim)}", texto, ""]
    return "\n".join(linhas)


def _yt_dlp(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["yt-dlp", *args], capture_output=True, text=True, check=False)


def baixar_legenda(url: str, idioma: str = "pt-orig") -> list[tuple[int, str]] | None:
    """Legenda automática em json3 -> cues. `None` quando o vídeo não tem legenda."""
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "%(id)s.%(ext)s"
        _yt_dlp(
            [
                "--skip-download",
                "--write-auto-subs",
                "--sub-langs",
                idioma,
                "--sub-format",
                "json3",
                "--no-warnings",
                "-o",
                str(saida),
                url,
            ]
        )
        arquivos = list(Path(tmp).glob("*.json3"))
        if not arquivos:
            return None
        dados = json.loads(arquivos[0].read_text(encoding="utf-8"))
    return agrupar_eventos([e for e in dados.get("events", []) if e.get("segs")])


def exigir_conteudo(cues: list[tuple[int, str]], origem: str) -> list[tuple[int, str]]:
    """Transcrição vazia é erro, não arquivo vazio.

    A primeira versão gravava o VTT sem cue nenhum e seguia em frente: a aula entrava
    no corpus como um arquivo válido e vazio, que nenhuma métrica denunciaria.
    """
    if not cues:
        raise RuntimeError(f"{origem} não produziu transcrição — nada foi gravado")
    return cues


def extrair_audio(url: str, destino: Path) -> None:
    """Baixa o áudio e entrega WAV 16k mono PEGANDO UM CANAL, não a soma dos dois.

    Medido em 2026-09-24: os dois canais destes vídeos estão em oposição de fase. O
    arquivo mede -31 dB em estéreo e -80 dB depois de somado em mono — silêncio. O
    faster-whisper converte para mono internamente, então transcrevia o cancelamento
    e devolvia alucinação sobre silêncio ("você pode fazer ummäßig"), sem erro algum.
    `pan=mono|c0=c0` descarta o canal direito e preserva a fala.
    """
    with tempfile.TemporaryDirectory() as tmp:
        bruto = Path(tmp) / "audio.m4a"
        r = _yt_dlp(["-f", "bestaudio[ext=m4a]/bestaudio", "-o", str(bruto), "--no-warnings", url])
        if not bruto.exists():
            raise RuntimeError(f"falha ao baixar o áudio de {url}: {r.stderr.strip()[:200]}")
        ff = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(bruto),
                "-af",
                "pan=mono|c0=c0",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(destino),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if not destino.exists():
            raise RuntimeError(f"ffmpeg falhou ao decodificar o áudio: {ff.stderr.strip()[:200]}")


def transcrever(url: str, modelo: str = "small") -> list[tuple[int, str]]:
    """Sem legenda no YouTube: baixa o áudio e transcreve localmente (faster-whisper).

    `vad_filter` fica DESLIGADO: com o áudio cancelado ele devolvia zero segmento, e
    um filtro que pode zerar a transcrição inteira não é o que se quer no caminho que
    constrói o corpus.
    """
    from faster_whisper import WhisperModel

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        extrair_audio(url, wav)
        wm = WhisperModel(modelo, device="cpu", compute_type="int8")
        segmentos, _info = wm.transcribe(str(wav), language="pt", vad_filter=False, beam_size=5)
        cues = [
            (int(s.start * 1000), " ".join(s.text.split())) for s in segmentos if s.text.strip()
        ]
    return exigir_conteudo(cues, f"whisper {modelo}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Monta o corpus de vídeo a partir do fontes.json")
    p.add_argument("--raiz", type=Path, default=RAIZ_PADRAO)
    p.add_argument("--forcar", action="store_true", help="refaz transcrições já existentes")
    p.add_argument("--transcrever", action="store_true", help="usa Whisper quando não há legenda")
    p.add_argument("--modelo", default="small", help="modelo do Whisper (tiny|base|small|medium)")
    args = p.parse_args(argv)

    mapa = json.loads((args.raiz / "fontes.json").read_text(encoding="utf-8"))
    sem_legenda: list[str] = []
    for caminho, url in sorted(mapa.items()):
        destino = args.raiz / caminho
        if destino.exists() and not args.forcar:
            print(f"· {caminho} — já existe")
            continue
        cues = baixar_legenda(url)
        origem = "legenda automática"
        if cues is None:
            if not args.transcrever:
                sem_legenda.append(caminho)
                print(f"! {caminho} — sem legenda no YouTube (use --transcrever)", file=sys.stderr)
                continue
            print(f"… {caminho} — sem legenda; transcrevendo com Whisper ({args.modelo})")
            cues, origem = transcrever(url, args.modelo), f"whisper {args.modelo}"
        exigir_conteudo(cues, origem)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(montar_vtt(cues), encoding="utf-8")
        chars = sum(len(t) for _, t in cues)
        print(f"✓ {caminho} — {len(cues)} cues, {chars:,} chars ({origem})")
    if sem_legenda:
        print(
            f"\n{len(sem_legenda)} aula(s) sem transcrição. Rode com --transcrever.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
