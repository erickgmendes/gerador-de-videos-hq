"""Prompts e blocos fixos usados na geração de prompts de imagem.

Baseado em `Documents/03. PROMPT PARA CRIAÇÃO DAS IMAGENS DOS
QUADRINHOS.docx`, com uma diferença deliberada: o docx pede que a IA
repita ~200 palavras de estilo/negative-prompt idênticas em cada painel
(pensado para um humano copiar/colar manualmente prompt por prompt). Como
aqui o pipeline é programático, a IA só escreve a parte criativa
(descrição da cena + personagens) e o código monta o resto — mesma
filosofia já usada na Fase 2 (narração vs. extração de cenas). Isso corta
o volume de tokens e garante que o bloco de estilo saia sempre idêntico
(sem risco de a IA "derivar" o texto ao longo de dezenas de painéis).
"""

from __future__ import annotations

import json

IMAGE_PROMPT_SYSTEM_PROMPT = """\
Você transforma uma cena de um roteiro de narração bíblica em uma
sequência de painéis de quadrinho, cada um descrito para gerar UMA ÚNICA
imagem (nunca página completa, nunca múltiplos painéis numa imagem só).

Você recebe: dados da cena (local, momento, ação, emoção, trecho da
narração), a quantidade exata de painéis a gerar para esta cena, os
nomes dos personagens mencionados nesta cena, a descrição visual de
TODOS os personagens já definidos em cenas anteriores deste mesmo
projeto e a descrição visual de TODOS os cenários/locais já definidos em
cenas anteriores (ambos podem estar vazios, se esta for a primeira cena).

REGRA MAIS IMPORTANTE — CONTINUIDADE DE PERSONAGENS:
Um mesmo personagem pode ser citado com nomes ou títulos diferentes em
cenas diferentes (ex.: "Gabriel", "o anjo Gabriel" e "Angel Gabriel" são
A MESMA pessoa; "Zacarias" e "o sacerdote" podem ser a mesma pessoa,
dependendo do contexto). Antes de descrever qualquer personagem desta
cena, verifique se ele já corresponde a alguém na lista de personagens
já definidos — pelo papel na história e pelo contexto, não só pelo texto
exato do nome. Se corresponder, use a descrição EXISTENTE
PALAVRA POR PALAVRA nos painéis desta cena — não a reescreva, não a
resuma, não mude nenhum detalhe (idade, roupa, cor, altura...), e NÃO
inclua esse nome em "new_characters". Só crie uma descrição nova para um
personagem que genuinamente ainda não existe na lista.

REGRA IGUALMENTE IMPORTANTE — CONTINUIDADE DE CENÁRIOS:
O mesmo princípio vale para o LOCAL da cena. "o templo", "o Templo de
Jerusalém" e "o salão principal do templo" podem ser o mesmo cenário
físico revisitado em cenas diferentes. Antes de descrever qualquer
cenário desta cena, verifique se ele já corresponde a algum cenário na
lista de cenários já definidos — pelo local narrativo e pelo contexto,
não só pelo texto exato do nome. Se corresponder, reaproveite a
descrição EXISTENTE PALAVRA POR PALAVRA (arquitetura, materiais, cores,
iluminação, objetos) em todo painel desta cena que se passe nesse
mesmo cenário, e NÃO inclua esse nome em "new_locations". Só crie uma
descrição nova para um cenário que genuinamente ainda não existe na
lista, ou quando a cena explicitamente se passa num lugar diferente.

REGRA IGUALMENTE IMPORTANTE — CONTINUIDADE DENTRO DA MESMA CENA:
Todos os painéis pedidos agora pertencem à MESMA cena contínua no tempo
— eles serão exibidos em sequência, como frames consecutivos de um único
momento. Portanto, a menos que a ação da cena explicitamente mova um
personagem para outro local ou o faça trocar de roupa (ex.: veste uma
capa, entra na água), TODOS os painéis desta cena devem repetir, palavra
por palavra, a mesma descrição de roupa/aparência de cada personagem E a
mesma descrição de cenário (arquitetura, iluminação, hora do dia, clima,
objetos de fundo) usada no primeiro painel em que aparecem. O que pode
(e deve) variar de painel para painel dentro da cena é só: pose corporal,
posição no espaço, expressão facial, gesto, estágio da ação, e o
enquadramento/ângulo de câmera ("shot_type"). Nunca mude cor de roupa,
estilo de roupa, iluminação geral ou elementos arquitetônicos de um
painel para o outro dentro da mesma cena sem justificativa na ação.

OUTRAS REGRAS (baseadas na Bíblia visual dos personagens, quando fornecida):
- Para personagens genuinamente novos: crie uma descrição visual
  completa e coerente com o contexto histórico/bíblico — sexo, idade
  aparente, altura, tipo físico, tom de pele, rosto, olhos, cabelo,
  barba (quando aplicável), roupas, cores, tecidos, calçados, acessórios.
  Não invente características extravagantes; a escolha deve parecer
  natural dentro do mundo bíblico retratado. As proporções corporais
  devem ser anatomicamente realistas e humanas — nunca descreva ou
  sugira braços, antebraços ou mãos alongados/maiores que o normal.
  Escreva em inglês. Dê a ele um nome canônico único (evite variações
  como "Anjo X" numa cena e só "X" noutra — prefira sempre o nome mais
  específico e completo).
- Para cenários genuinamente novos: crie uma descrição visual completa
  do local — arquitetura, materiais, cores, época do dia, iluminação,
  clima, objetos e elementos de fundo característicos. Escreva em
  inglês. Dê a ele um nome canônico único e específico (ex.: "Zacarias'
  House Courtyard", não só "House").
- Para CADA painel, escreva uma descrição autossuficiente em inglês que
  incorpore a aparência COMPLETA de cada personagem presente (nunca só o
  nome) e a descrição COMPLETA do cenário — a ferramenta que vai gerar a
  imagem não tem acesso a nada além do texto deste painel. Nunca escreva
  "same as before", "as previously described" ou qualquer referência
  externa. Isso vale mesmo repetindo a descrição inteira em todo painel
  em que o personagem/cenário aparecer.
- Descreva a ação, posição corporal, expressão e emoção de acordo com a
  cena. Quando o roteiro não especificar o local exatamente, mantenha
  plausibilidade histórica sem contradizer a Escritura.
- Quando a cena envolver anjos, milagres ou manifestações divinas,
  descreva com luz celestial, raios divinos, atmosfera majestosa e
  grandiosa, mas ainda dentro da linguagem de quadrinho vintage — mesmo
  assim, mantenha esses elementos idênticos entre os painéis da mesma
  cena (regra de continuidade acima).
- Gere painéis com enquadramentos variados quando fizer sentido (plano
  geral, plano médio, close-up, ângulo baixo/alto) — a escolha deve
  servir à narrativa, não ser aleatória. Indique o enquadramento escolhido
  no campo "shot_type" de cada painel (em inglês, ex.: "medium shot").
- NÃO inclua o bloco de estilo artístico, formato, proibição de texto ou
  negative prompt — isso é adicionado automaticamente depois. Escreva
  SOMENTE a descrição da cena/personagens/cenário de cada painel.
- NÃO inclua diálogos como texto visível — a imagem final não pode ter
  nenhum texto (isso também é garantido automaticamente depois).

Responda APENAS com um objeto JSON válido, sem markdown, sem comentários,
sem texto antes ou depois, no formato exato:

{"new_characters": {"Nome": "descrição visual completa em inglês"}, "new_locations": {"Nome": "descrição visual completa em inglês"}, "panels": [{"shot_type": "...", "description": "..."}]}

O array "panels" deve conter exatamente a quantidade de painéis pedida,
na ordem em que devem aparecer. "new_characters" e "new_locations" devem
conter APENAS personagens/cenários genuinamente novos — objetos vazios
{} sempre que tudo na cena já corresponder a algo já definido."""


def build_scene_user_message(
    *,
    location: str,
    time: str,
    action: str,
    emotion: str,
    narration_excerpt: str,
    panel_count: int,
    scene_characters: list[str],
    known_characters: dict[str, str],
    known_locations: dict[str, str],
    biblia_visual_text: str | None,
) -> str:
    parts = [
        f"CENA:\nLocal: {location}\nMomento: {time}\nAção: {action}\nEmoção: {emotion}",
        f"NARRAÇÃO DESTA CENA:\n{narration_excerpt}",
        "PERSONAGENS MENCIONADOS NESTA CENA: "
        + (", ".join(scene_characters) if scene_characters else "(nenhum citado explicitamente)"),
        f"QUANTIDADE DE PAINÉIS A GERAR: {panel_count}",
    ]
    if known_characters:
        parts.append(
            "PERSONAGENS JÁ DEFINIDOS EM CENAS ANTERIORES (verifique por contexto/papel, não só pelo "
            "texto do nome, antes de considerar alguém novo — ver regra de continuidade):\n"
            + json.dumps(known_characters, ensure_ascii=False, indent=2)
        )
    if known_locations:
        parts.append(
            "CENÁRIOS JÁ DEFINIDOS EM CENAS ANTERIORES (verifique por contexto/local, não só pelo "
            "texto do nome, antes de considerar um cenário novo — ver regra de continuidade):\n"
            + json.dumps(known_locations, ensure_ascii=False, indent=2)
        )
    if biblia_visual_text and biblia_visual_text.strip():
        parts.append(f"BÍBLIA VISUAL DOS PERSONAGENS (referência):\n{biblia_visual_text}")
    return "\n\n".join(parts)


# Estilo artístico completo (seção 16 do docx 03) — repetido integralmente
# em TODO prompt, mas montado aqui pelo código, nunca redigitado pela IA.
_STYLE_BLOCK = (
    "A science fiction comic strip from an American Sunday newspaper from the early 1930s, "
    "faithfully preserving the visual language of Alex Raymond's early Flash Gordon works: "
    "elegant hand-drawn ink lines, expressive brushstrokes, realistic and highly detailed human "
    "anatomy with correct, true-to-life body proportions (head-to-body ratio, arm length, forearm "
    "length, and hand size must all match real human anatomy — heroic and idealized physique, but "
    "never elongated or oversized limbs or hands), dramatic cinematic compositions, strong black shadows, "
    "extensive cross-shading, fine etching-style details, science fiction Art Deco architecture, "
    "exotic alien landscapes, dramatic perspective, dynamic vision of the future, saturated "
    "outlines but with a vintage four-color touch, hand-painted comic book colors, cream paper "
    "highlights, subtle printing imperfections, striking black outlines, watercolor color fills, "
    "theatrical lighting, pulp adventure atmosphere, no modern digital rendering, no "
    "photorealism, no anime, no manga, no 3D CGI. The artwork must feel like a meticulously "
    "hand-drawn and hand-colored American newspaper adventure comic from the early 1930s, while "
    "remaining an original visual interpretation and not reproducing any specific existing comic "
    "panel, page, character pose, or copyrighted artwork."
)

# Seção 20 do docx 03.
_QUALITY_BLOCK = (
    "16:9 aspect ratio, high resolution, highly detailed hand-drawn comic artwork, detailed ink "
    "work, realistic anatomy with correct human body proportions, accurately sized arms, forearms, "
    "hands and legs relative to the torso and head, detailed facial features, detailed clothing, "
    "detailed environment, cinematic composition, dramatic lighting, vintage printed comic texture, "
    "hand-painted colors."
)

# Seção 19 do docx 03 — proibição absoluta de texto.
_NO_TEXT_BLOCK = (
    "No text anywhere in the image. No speech balloons, no thought balloons, no captions, no "
    "narration boxes, no subtitles, no title, no letters, no numbers, no written words, no "
    "character names, no signs with writing, no inscriptions, no logos, no watermark, no "
    "signature, no typography."
)

# Seção 21 do docx 03.
_NEGATIVE_BLOCK = (
    "Negative prompt: photorealism, modern clothing, modern objects, modern architecture, "
    "contemporary fashion, modern technology, anime, manga, 3D CGI, plastic-looking characters, "
    "inconsistent facial features, inconsistent age, inconsistent body proportions, different "
    "hair color, different eye color, incorrect beard, incorrect clothing, historically "
    "inaccurate clothing, malformed anatomy, extra limbs, malformed hands, distorted faces, "
    "elongated limbs, elongated arms, elongated forearms, stretched limbs, oversized hands, "
    "oversized forearms, undersized head, disproportionate body parts, incorrect limb-to-body "
    "ratio, unnaturally long arms, unnaturally long hands, gigantism, "
    "duplicated characters, text, letters, numbers, words, speech balloons, thought balloons, "
    "captions, narration boxes, subtitles, title, signs, inscriptions, logos, watermark, "
    "signature, typography."
)


def _flatten(text: str) -> str:
    """Colapsa qualquer quebra de linha (inclusive linha em branco) num
    espaço só. A ferramenta externa de imagem separa um prompt do outro
    por linha em branco (seção 22) — uma quebra DENTRO de um prompt faz
    ela interpretar um painel só como vários prompts (bug real relatado
    pelo usuário). Aplicado tanto na descrição vinda da IA (que podia, em
    tese, devolver texto em múltiplos parágrafos) quanto nos blocos fixos."""
    return " ".join(text.split())


def build_panel_prompt_text(description: str, shot_type: str) -> str:
    shot = f"SINGLE COMIC PANEL. {shot_type}." if shot_type else "SINGLE COMIC PANEL."
    parts = [description, shot, _STYLE_BLOCK, _QUALITY_BLOCK, _NO_TEXT_BLOCK, _NEGATIVE_BLOCK]
    return " ".join(_flatten(part) for part in parts)
