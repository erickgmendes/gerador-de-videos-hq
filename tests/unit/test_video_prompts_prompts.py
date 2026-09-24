"""Regressão: mesmo motivo de tests/unit/test_image_prompts_prompts.py —
a ferramenta externa separa um prompt do outro por linha em branco, então
o prompt de vídeo (mesmo sendo fixo) não pode ter nenhuma quebra de linha
dentro dele."""

from app.services.video_prompts.prompts import build_video_prompt_text


def test_build_video_prompt_text_has_no_line_breaks():
    result = build_video_prompt_text(5.0)

    assert "\n" not in result
    assert "\r" not in result


def test_build_video_prompt_text_is_identical_for_the_same_duration():
    # O texto é fixo (não gerado por IA) — chamadas repetidas com a mesma
    # duração devem devolver exatamente o mesmo texto, sempre.
    first = build_video_prompt_text(5.0)
    second = build_video_prompt_text(5.0)

    assert first == second


def test_build_video_prompt_text_includes_duration_hint():
    result = build_video_prompt_text(5.0)
    assert "5 seconds" in result

    result_fractional = build_video_prompt_text(4.5)
    assert "4.5 seconds" in result_fractional


def test_build_video_prompt_text_forbids_illicit_content_but_allows_wine():
    result = build_video_prompt_text(5.0)

    assert "drug" in result.lower()
    assert "sexual" in result.lower()
    assert "illegal" in result.lower()
    assert "wine" in result.lower()
    assert "ALLOWED" in result


def test_build_video_prompt_text_asks_for_restrained_motion():
    result = build_video_prompt_text(5.0)
    assert "subtle" in result.lower()
    assert "solemn" in result.lower()
