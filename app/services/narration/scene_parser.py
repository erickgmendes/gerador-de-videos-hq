"""Parsing determinístico (sem IA) do texto de narração no formato
`CENA N — Título / Local: / Momento: / Narração:` para uma lista de cenas
"cruas". O texto de narração de cada cena é extraído literalmente — nunca
reescrito — porque é o que futuramente alimenta o TTS (Fase 3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

WORDS_PER_MINUTE = 155.0


# Modelos frequentemente decoram o roteiro com markdown (**negrito**, ###
# títulos) apesar da instrução de saída "só o roteiro" — confirmado ao
# vivo (Groq envolveu cada "CENA N — Título" em **negrito**). Os padrões
# abaixo toleram decoração `#`/`*`/`_` ao redor de cabeçalhos e rótulos
# sem exigi-la, para não depender de um formato exato demais.
_SCENE_HEADER_RE = re.compile(
    r"^[ \t]*[#*_]*[ \t]*CENA\s+(\d+)\s*[—\-–:]\s*(.*?)[ \t]*[#*_]*[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
_LOCAL_RE = re.compile(
    r"[#*_]*Local[#*_]*\s*:\s*(.*?)(?=\n\s*[#*_]*Momento[#*_]*\s*:|\n\s*[#*_]*Narra[çc][ãa]o[#*_]*\s*:|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_MOMENTO_RE = re.compile(
    r"[#*_]*Momento[#*_]*\s*:\s*(.*?)(?=\n\s*[#*_]*Narra[çc][ãa]o[#*_]*\s*:|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_NARRACAO_RE = re.compile(r"[#*_]*Narra[çc][ãa]o[#*_]*\s*:\s*(.*)", re.IGNORECASE | re.DOTALL)


@dataclass
class RawScene:
    order: int
    title: str
    location: str
    time: str
    narration: str
    estimated_duration: float


def _clean(text: str) -> str:
    return re.sub(r"\n{2,}", "\n\n", text.strip())


def estimate_duration_seconds(text: str) -> float:
    word_count = len(text.split())
    return round(word_count / WORDS_PER_MINUTE * 60, 1)


def parse_scene_blocks(narration_text: str) -> list[RawScene]:
    headers = list(_SCENE_HEADER_RE.finditer(narration_text))
    scenes: list[RawScene] = []

    for index, header in enumerate(headers):
        order = int(header.group(1))
        title = header.group(2).strip()
        block_start = header.end()
        block_end = headers[index + 1].start() if index + 1 < len(headers) else len(narration_text)
        block = narration_text[block_start:block_end]

        location_match = _LOCAL_RE.search(block)
        time_match = _MOMENTO_RE.search(block)
        narration_match = _NARRACAO_RE.search(block)

        narration = _clean(narration_match.group(1)) if narration_match else ""
        if not narration:
            continue

        scenes.append(
            RawScene(
                order=order,
                title=title,
                location=_clean(location_match.group(1)) if location_match else "",
                time=_clean(time_match.group(1)) if time_match else "",
                narration=narration,
                estimated_duration=estimate_duration_seconds(narration),
            )
        )

    return scenes
