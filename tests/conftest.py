"""Fixtures compartilhadas.

Testes que exigem Qdrant ou OpenAI vao em tests/integration/ e levam a marca
`@pytest.mark.integration`, para o CI conseguir rodar so os unitarios.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def samples_dir() -> Path:
    """Corpus aberto, o mesmo que o CI e a demo usam."""
    return REPO_ROOT / "samples"


@pytest.fixture
def texto_com_pii() -> str:
    """Texto sintetico para os testes de anonimizacao (FR-12)."""
    return (
        "Fala pessoal, quem tiver duvida manda pro contato@exemplo.com.br "
        "ou chama no (11) 98765-4321. Meu CPF pro cadastro e 123.456.789-09."
    )


VTT_EXEMPLO = """WEBVTT

00:00:00.000 --> 00:00:04.000
Bem-vindos à aula sobre funil de vendas.

00:00:04.000 --> 00:00:10.000
O funil de vendas tem etapas claras: topo, meio e fundo.

00:00:10.000 --> 00:00:16.000
No topo atraimos visitantes, no meio nutrimos, no fundo convertemos.
"""

SRT_EXEMPLO = """1
00:00:00,000 --> 00:00:04,000
Bem-vindos à aula de precificação.

2
00:00:04,000 --> 00:00:09,000
Preço por valor captura o que o cliente está disposto a pagar.
"""

MD_EXEMPLO = """# Aula 4 — CAC e LTV

> Conteúdo de exemplo para os testes.

## Custo de Aquisição de Cliente (CAC)

O CAC é o custo total de aquisição dividido pelo número de clientes conquistados no
mesmo período. Custo total inclui mídia, salários do time comercial e ferramentas.

## Lifetime Value (LTV)

O LTV estima quanto um cliente gera de receita ao longo do relacionamento.
"""


def _make_pdf(text: str) -> bytes:
    """PDF mínimo e válido, com um objeto de texto por página.

    Gerar em runtime evita commitar binário (o .gitignore exclui *.pdf fora de samples/).
    """
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF"
    ).encode()
    return bytes(out)


def _corpus_dir(tmp_path: Path) -> Path:
    d = tmp_path / "curso-exemplo"
    (d / "modulo-2-metricas").mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def vtt_file(tmp_path: Path) -> Path:
    f = _corpus_dir(tmp_path) / "modulo-2-metricas" / "aula-05-funil.vtt"
    f.write_text(VTT_EXEMPLO, encoding="utf-8")
    return f


@pytest.fixture
def srt_file(tmp_path: Path) -> Path:
    f = _corpus_dir(tmp_path) / "modulo-3-estrategia" / "aula-07-precificacao.srt"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(SRT_EXEMPLO, encoding="utf-8")
    return f


@pytest.fixture
def md_file(tmp_path: Path) -> Path:
    f = _corpus_dir(tmp_path) / "modulo-2-metricas" / "aula-04-cac-e-ltv.md"
    f.write_text(MD_EXEMPLO, encoding="utf-8")
    return f


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    f = _corpus_dir(tmp_path) / "modulo-1-fundamentos" / "aula-01-intro.pdf"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(_make_pdf("O CAC e o custo de aquisicao de clientes."))
    return f


#: Dossiê de mentoria: transcrição seccionada por `### [HH:MM:SS]`.
#: Blocos com tamanho realista (~1,9KB no corpus real) para exercitar o agrupamento.
DOSSIE_EXEMPLO = """# Fulano de Tal - Narrativa e Monetizacao
## Programa: FLG T04 - Founder Led Growth Turma 04
### Escola Exemplo | Dossier Completo para Consulta

> **Mentor:** CMO senior, 1M seguidores.

---

## Transcricao Integral e Organizada

### [00:28:33]

**Mentor:** Narrativa e uma serie de acontecimentos encadeados que leva o cliente de frio para
morno. Nao e qualquer historia: e a que termina em compra. Todo mundo fala que quer lead
quente, mas ninguem sabe definir o que e um lead quente. Lead quente e o que ja atravessou a
sua narrativa inteira e chegou do outro lado sabendo por que voce, e nao o concorrente. Isso
nao se compra com trafego pago, se constroi com sequencia de conteudo. E a sequencia importa
mais que a peca isolada, porque o que move a pessoa e o acumulo, nao o post. Repare que ninguem
compra no primeiro contato: compra no setimo, no decimo, depois de ver voce resolver o problema
de outra pessoa parecida com ela.

### [00:30:34]

**Mentor:** Bloco curto.

### [00:32:36]

**Mentor:** Comeca pelo YouTube, porque o tempo de atencao la e muito maior. No Instagram a
pessoa te ve por um minuto e meio e nao lembra do seu nome. No YouTube ela senta, liga na TV e
fica quarenta minutos. Ela aprende seu nome, sua historia, o nome da sua empresa. Para B2B isso
vale ainda mais, porque o ciclo de decisao e longo e a pessoa precisa confiar antes de pedir
proposta. Entao o caminho e: video longo no YouTube respondendo duvida real de cliente, recorte
disso no Instagram, e trafego pago so depois que o organico validou. E medir sempre pelo custo
de aquisicao, nunca pelo numero de seguidores, porque seguidor sem receita e vaidade cara e
demora a aparecer no caixa.
"""


@pytest.fixture
def dossie_file(tmp_path: Path) -> Path:
    f = _corpus_dir(tmp_path) / "modulo-1-fundamentos" / "aula-06-fulano-narrativa.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(DOSSIE_EXEMPLO, encoding="utf-8")
    return f
