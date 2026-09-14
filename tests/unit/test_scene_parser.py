from app.services.narration.scene_parser import estimate_duration_seconds, parse_scene_blocks

SAMPLE_NARRATION = """\
CENA 1 — O chamado à beira-mar
Local:
Às margens do mar da Galileia
Momento:
Início da manhã
Narração:
O sol ainda mal despontava sobre as águas quando Jesus caminhava pela
praia. Ao longe, alguns pescadores recolhiam suas redes.

CENA 2 — A resposta imediata
Local:
Ainda às margens do mar
Momento:
Pouco depois
Narração:
Simão e André largaram as redes e o seguiram, sem hesitar.
"""


def test_parse_scene_blocks_extracts_all_scenes():
    scenes = parse_scene_blocks(SAMPLE_NARRATION)

    assert len(scenes) == 2
    assert scenes[0].order == 1
    assert scenes[0].title == "O chamado à beira-mar"
    assert scenes[0].location == "Às margens do mar da Galileia"
    assert scenes[0].time == "Início da manhã"
    assert "Jesus caminhava pela" in scenes[0].narration
    assert scenes[1].order == 2
    assert "Simão e André" in scenes[1].narration


def test_parse_scene_blocks_returns_empty_for_unstructured_text():
    scenes = parse_scene_blocks("Isto não segue o formato de cenas esperado.")
    assert scenes == []


def test_parse_scene_blocks_tolerates_hyphen_and_colon_separators():
    text = "CENA 1 - Título com hífen\nLocal:\nUm lugar\nMomento:\nUma hora\nNarração:\nTexto da cena."
    scenes = parse_scene_blocks(text)
    assert len(scenes) == 1
    assert scenes[0].title == "Título com hífen"


def test_parse_scene_blocks_tolerates_markdown_bold_headers_and_labels():
    # Reproduz um comportamento real observado com o Groq: o modelo envolve
    # o cabeçalho da cena em **negrito** apesar da instrução de saída "só o
    # roteiro" — o parser não pode depender de ausência de markdown.
    text = (
        "**CENA 1 — O chamado à beira-mar**  \n"
        "Local: Às margens do mar da Galileia  \n"
        "Momento: Início da manhã  \n"
        "Narração:\n"
        "O sol ainda mal despontava quando Jesus caminhava pela praia.\n\n"
        "**CENA 2 — A resposta imediata**\n\n"
        "Local: Ainda às margens do mar\n"
        "Momento: Pouco depois\n"
        "Narração:\n"
        "Simão e André largaram as redes e o seguiram, sem hesitar.\n"
    )

    scenes = parse_scene_blocks(text)

    assert len(scenes) == 2
    assert scenes[0].title == "O chamado à beira-mar"
    assert scenes[0].location == "Às margens do mar da Galileia"
    assert "Jesus caminhava pela praia" in scenes[0].narration
    assert scenes[1].title == "A resposta imediata"


def test_estimate_duration_seconds_scales_with_word_count():
    short = estimate_duration_seconds("uma frase curta de teste")
    long = estimate_duration_seconds(" ".join(["palavra"] * 155))
    assert short < long
    assert long == 60.0
