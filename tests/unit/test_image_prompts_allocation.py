"""Testa o teto de imagens do projeto (MAX_IMAGE_PROMPTS) — pedido do
usuário para editar manualmente no Kdenlive num primeiro momento, sem
depender de uma imagem a cada poucos segundos de áudio."""

from app.services.image_prompts.service import allocate_panel_counts, compute_panel_count


def test_allocate_panel_counts_uses_ideal_when_under_the_cap():
    durations = {"s1": 10.0, "s2": 8.0}

    allocation = allocate_panel_counts(durations, segment_seconds=5.0, max_total=50)

    assert allocation == {"s1": compute_panel_count(10.0, 5.0), "s2": compute_panel_count(8.0, 5.0)}


def test_allocate_panel_counts_caps_total_when_ideal_exceeds_it():
    # 18 cenas de ~26s cada (o caso real do usuário) — ideal seria ~104
    # painéis (26/5 arredondado para cima = 6 por cena × 18).
    durations = {f"s{i}": 26.0 for i in range(18)}

    allocation = allocate_panel_counts(durations, segment_seconds=5.0, max_total=50)

    assert sum(allocation.values()) == 50
    assert all(count >= 1 for count in allocation.values())


def test_allocate_panel_counts_distributes_proportionally_to_duration():
    # Cena longa deve continuar recebendo mais painéis que a curta, só numa
    # escala reduzida — não "todo mundo recebe o mesmo".
    durations = {"long": 100.0, "short": 10.0}

    allocation = allocate_panel_counts(durations, segment_seconds=5.0, max_total=10)

    assert sum(allocation.values()) == 10
    assert allocation["long"] > allocation["short"]


def test_allocate_panel_counts_never_gives_zero_panels_even_with_many_scenes():
    # Mais cenas do que o teto — cada uma ainda recebe pelo menos 1,
    # mesmo que isso estoure o teto combinado.
    durations = {f"s{i}": 5.0 for i in range(80)}

    allocation = allocate_panel_counts(durations, segment_seconds=5.0, max_total=50)

    assert len(allocation) == 80
    assert all(count >= 1 for count in allocation.values())
    assert sum(allocation.values()) == 80


def test_allocate_panel_counts_empty_input():
    assert allocate_panel_counts({}, segment_seconds=5.0, max_total=50) == {}


def test_allocate_panel_counts_total_matches_cap_across_varied_durations():
    # Distribuição bem desigual — garante que o método dos maiores restos
    # sempre fecha exatamente no teto, sem sobrar nem faltar unidade.
    durations = {"a": 5.0, "b": 47.0, "c": 12.0, "d": 3.0, "e": 90.0}

    allocation = allocate_panel_counts(durations, segment_seconds=5.0, max_total=20)

    assert sum(allocation.values()) == 20
