"""FR-10, FR-11: um loader por formato; load_directory não conhece a origem do corpus."""

from grifo.ingest.loaders import (
    load_directory,
    load_markdown,
    load_pdf,
    load_srt,
    load_vtt,
)


def test_load_directory_despacha_por_formato(md_file, vtt_file, srt_file, pdf_file):
    """FR-10: o mesmo comando indexa qualquer diretório, sem alteração de código."""
    corpus = md_file.parent.parent.parent
    docs = load_directory(corpus, curso="Curso Exemplo")
    fontes = {d.metadata["fonte_tipo"] for d in docs}
    assert {"markdown", "transcricao", "pdf"} <= fontes
    assert all(d.metadata["curso"] == "Curso Exemplo" for d in docs)
    assert all(d.page_content.strip() for d in docs)


def test_load_directory_ignora_extensao_desconhecida(md_file, tmp_path):
    (md_file.parent / "notas.txt").write_text("ignorar", encoding="utf-8")
    docs = load_directory(md_file.parent.parent.parent)
    assert all(d.metadata["arquivo"].endswith((".md", ".vtt", ".srt", ".pdf")) for d in docs)


def test_load_directory_exige_diretorio(md_file):
    import pytest

    with pytest.raises(NotADirectoryError):
        load_directory(md_file)


def test_load_directory_pula_arquivo_fora_da_estrutura_de_modulo(md_file, capsys):
    """ADR 003: arquivo sem diretório modulo-<n>-<slug> vira citação lixo — não indexa."""
    corpus = md_file.parent.parent.parent
    (corpus / "README.md").write_text(
        "# Sobre o corpus\n\nDocumentação, não aula.", encoding="utf-8"
    )
    docs = load_directory(corpus)
    modulos = {d.metadata["modulo"] for d in docs}
    assert corpus.name not in modulos  # o README da raiz não vira "modulo samples"
    assert all(d.metadata["arquivo"] != "README.md" for d in docs)
    assert "pulados" in capsys.readouterr().err


def test_load_markdown_quebra_por_secao_e_extrai_aula_do_heading(md_file):
    docs = load_markdown(md_file)
    assert len(docs) == 3  # intro + CAC + LTV
    assert docs[0].metadata["aula"] == "4 - CAC e LTV"
    assert docs[0].metadata["modulo"] == "2 - Metricas"
    assert "custo total de aquisição" in docs[1].page_content
    assert all(d.metadata["pagina"] for d in docs)  # invariante DC-1 para markdown


def test_load_vtt_traz_timestamp_inicio_e_texto(vtt_file):
    docs = load_vtt(vtt_file)
    assert docs[0].metadata["timestamp_inicio"] == "00:00:00"
    assert "funil de vendas" in docs[0].page_content
    assert docs[0].metadata["aula"] == "5 - Funil"
    assert docs[0].metadata["fonte_tipo"] == "transcricao"


def test_load_srt_traz_timestamp_inicio(srt_file):
    docs = load_srt(srt_file)
    assert docs[0].metadata["timestamp_inicio"] == "00:00:00"
    assert "precificação" in docs[0].page_content.lower()


def test_load_pdf_pagina_e_texto_nao_vazio(pdf_file):
    docs = load_pdf(pdf_file)
    assert len(docs) == 1
    assert docs[0].metadata["pagina"] == 1
    assert docs[0].page_content.strip()
    assert docs[0].metadata["fonte_tipo"] == "pdf"


def test_dossie_de_mentoria_secciona_por_timestamp(dossie_file):
    """FR-33 no material real: cada `### [HH:MM:SS]` vira Document com o seu minuto.

    Sem isso a transcricao inteira colapsa numa secao so, o timestamp fica como ruido
    dentro do texto e a citacao perde o link para o ponto do video.
    """
    docs = load_markdown(dossie_file, curso="Curso Exemplo")
    stamps = [d.metadata["timestamp_inicio"] for d in docs if d.metadata["timestamp_inicio"]]
    # o bloco curto de 00:30:34 foi juntado ao seguinte, guardando o proprio minuto
    assert stamps == ["00:28:33", "00:30:34"]
    assert all(d.metadata["fonte_tipo"] == "transcricao" for d in docs)


def test_dossie_marca_fonte_tipo_transcricao(dossie_file):
    """`fonte_tipo` guia a limpeza de ruido no pipeline — .md aqui nao e markdown comum."""
    docs = load_markdown(dossie_file)
    assert {d.metadata["fonte_tipo"] for d in docs} == {"transcricao"}


def test_dossie_preserva_a_capa_da_sessao(dossie_file):
    """O preambulo (titulo, programa, bio do mentor) e a unica parte com contexto de
    quem fala: entra como pagina 1, satisfazendo o localizador do DC-1."""
    capa = load_markdown(dossie_file)[0]
    assert capa.metadata["pagina"] == 1
    assert capa.metadata["timestamp_inicio"] is None
    assert "Founder Led Growth" in capa.page_content


def test_dossie_junta_bloco_curto_mantendo_o_primeiro_timestamp(dossie_file):
    """Bloco minusculo so polui o top-k; ao juntar, o minuto citado e o do primeiro."""
    docs = load_markdown(dossie_file)
    bloco = next(d for d in docs if d.metadata["timestamp_inicio"] == "00:30:34")
    assert "Bloco curto." in bloco.page_content
    assert "YouTube" in bloco.page_content  # juntou com o bloco seguinte


def test_markdown_comum_continua_seccionando_por_heading(md_file):
    """Deteccao e por conteudo: sem timestamps, o caminho antigo segue valendo."""
    docs = load_markdown(md_file)
    assert all(d.metadata["fonte_tipo"] == "markdown" for d in docs)
    assert all(d.metadata["timestamp_inicio"] is None for d in docs)
    assert [d.metadata["pagina"] for d in docs] == list(range(1, len(docs) + 1))
