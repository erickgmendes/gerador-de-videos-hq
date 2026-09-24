"""Prompt fixo usado para animar cada painel de imagem já gerado (Fase 5).

Diferente da Fase 4 (prompts de imagem), aqui não há geração via IA: o
usuário pediu explicitamente um prompt genérico de animação — "não
precisa se atentar a detalhes, porque a imagem por si só já possui os
elementos visuais". O texto é o mesmo para todo painel, montado
inteiramente pelo código (mesma filosofia de blocos fixos da Fase 4, só
que aqui o prompt INTEIRO é fixo, não só o bloco de estilo) — sem chamada
de IA e sem cache de continuidade entre painéis, porque não há nada para
manter consistente: cada vídeo anima só a imagem que já foi aprovada e
enviada na Fase 4.
"""

from __future__ import annotations

# Instrução de animação — pede movimento sutil e cinematográfico sem
# alterar o conteúdo da imagem ("sem perder a essência"). Em inglês, mesma
# convenção da Fase 4 (ferramentas externas de geração funcionam melhor em
# inglês).
_ANIMATION_BLOCK = (
    "Animate this single static comic-panel image with subtle, natural, cinematic motion — "
    "bring it gently to life without altering its content. Preserve exactly the characters, "
    "their appearance, clothing, pose, the environment, the lighting, and the vintage "
    "hand-drawn comic art style already shown in the image — do not add, remove, redesign, or "
    "change any character, object, or element. Keep identity and anatomy fully stable and "
    "consistent across the whole clip — no morphing, no warping, no extra or missing limbs, no "
    "face swapping. Motion should be minimal and restrained: gentle camera movement (slow pan, "
    "slow zoom, or subtle parallax), soft environmental motion (drifting dust or light "
    "particles, flickering flame or torchlight, gentle wind moving hair, fabric, leaves, or "
    "water), and subtle character motion (breathing, blinking, a slight natural sway or shift "
    "in weight) fitting the scene's mood. No new characters, no new objects, no scene changes, "
    "no camera cuts, no scene teleportation."
)

# "e nem aloprar" — tom contido, nunca movimento frenético; é um roteiro
# bíblico solene, não uma cena de ação.
_RESTRAINT_BLOCK = (
    "Keep the motion slow, smooth, and reverent — this is a solemn, contemplative biblical "
    "narrative, not an action sequence. No fast movement, no shaking, no erratic camera, no "
    "chaotic motion."
)

# Bloco negativo pedido explicitamente pelo usuário: nunca deixar a
# ferramenta de animação "inventar" personagens bíblicos fazendo algo
# ilícito, sexual ou proibido — com a exceção explícita do vinho, bebida
# normal e historicamente correta para a época (não deve ser tratado como
# "droga" nem removido).
_NEGATIVE_BLOCK = (
    "Negative prompt: nudity, sexual content, sexual acts, suggestive or provocative behavior, "
    "illegal activity, drug use, drug paraphernalia, smoking, intoxication, violence, gore, "
    "blood, weapons used to harm, self-harm, occult or satanic imagery, disrespectful or "
    "mocking depiction of sacred or religious figures, modern clothing, modern objects, modern "
    "technology, anime, manga, 3D CGI, photorealism, morphing anatomy, extra limbs, malformed "
    "hands, distorted or flickering faces, character identity changing between frames, "
    "duplicated characters, text, subtitles, captions, watermark, logo, signature, sudden jump "
    "cuts, erratic or shaky camera, scene teleportation. Wine and other beverages typical of "
    "the biblical era, shown being poured or consumed moderately, are historically accurate and "
    "explicitly ALLOWED — never treat wine or its consumption as prohibited content."
)


def _flatten(text: str) -> str:
    """Mesmo motivo da Fase 4 (ver app/services/image_prompts/prompts.py):
    a ferramenta externa separa um prompt do outro por linha em branco —
    uma quebra DENTRO de um prompt faria ela interpretar um vídeo só como
    vários prompts."""
    return " ".join(text.split())


def build_video_prompt_text(clip_seconds: float) -> str:
    """Monta o prompt fixo de animação — idêntico para todo painel, exceto
    a duração sugerida do clipe (vem de Settings.video_segment_seconds, o
    mesmo valor que a Fase 4 já usa para calcular quantos painéis cada
    cena precisa — ver app/services/image_prompts/service.py)."""
    duration_hint = f"Suggested clip length: about {clip_seconds:g} seconds."
    parts = [_ANIMATION_BLOCK, _RESTRAINT_BLOCK, duration_hint, _NEGATIVE_BLOCK]
    return " ".join(_flatten(part) for part in parts)
