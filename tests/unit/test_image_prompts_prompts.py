"""Regressão: a ferramenta externa de geração de imagem separa um prompt
do outro por linha em branco — se o texto de UM prompt tiver uma quebra
de linha (ou pior, uma linha em branco) dentro dele, a ferramenta
interpreta um painel só como vários prompts. Relatado pelo usuário com um
exemplo real (o bloco de estilo/formato/negative, unidos com "\n\n",
virava 5 prompts extras)."""

from app.services.image_prompts.prompts import build_panel_prompt_text


def test_build_panel_prompt_text_has_no_line_breaks():
    result = build_panel_prompt_text(
        "Zacarias walks toward the city at dawn.", "wide shot"
    )

    assert "\n" not in result
    assert "\r" not in result


def test_build_panel_prompt_text_has_no_line_breaks_even_with_multiline_description():
    # A IA poderia, em tese, devolver a descrição em múltiplos parágrafos
    # — o código precisa achatar isso também, não só os blocos fixos.
    description = "First paragraph of the scene.\n\nSecond paragraph with more detail.\nThird line."

    result = build_panel_prompt_text(description, "close-up")

    assert "\n" not in result
    assert "First paragraph of the scene." in result
    assert "Second paragraph with more detail." in result
    assert "Third line." in result


def test_build_panel_prompt_text_includes_all_required_blocks():
    result = build_panel_prompt_text("A calm scene.", "medium shot")

    assert "SINGLE COMIC PANEL" in result
    assert "medium shot" in result
    assert "Alex Raymond" in result  # bloco de estilo
    assert "16:9 aspect ratio" in result  # bloco de qualidade/formato
    assert "No text anywhere in the image" in result  # proibição de texto
    assert "Negative prompt:" in result


def test_build_panel_prompt_text_omits_shot_type_when_empty():
    result = build_panel_prompt_text("A calm scene.", "")
    assert "SINGLE COMIC PANEL." in result
    assert "SINGLE COMIC PANEL. ." not in result
