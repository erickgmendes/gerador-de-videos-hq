"""Prompts usados pela geração de narração e pela extração de cenas.

O prompt de narração transcreve as regras de
`Documents/01. PROMPT PARA CRIAÇÃO DE ROTEIRO DE NARRAÇÃO BÍBLICA.docx`
(fidelidade à Escritura, ambientação, formato por cena, duração, tom,
estrutura). A extração de cenas é um segundo passo próprio desta
aplicação (não vem do docx): pega o roteiro já dividido em cenas pelo
`scene_parser` e pede apenas os campos semânticos que o parsing
determinístico não consegue extrair (personagens, ação, emoção,
importância visual) — nunca pede para repetir a narração, para não
correr o risco da IA reescrever o texto que será usado no TTS (Fase 3).
"""

from __future__ import annotations

import json

NARRATION_SYSTEM_PROMPT = """\
Você transforma uma leitura bíblica em um roteiro narrativo completo, \
envolvente e adequado para aproximadamente 20 minutos de narração (cerca \
de 2.400 a 3.000 palavras). A referência bíblica e o texto fornecidos \
pelo usuário são a autoridade máxima da narrativa.

FIDELIDADE ABSOLUTA À ESCRITURA
Não altere acontecimentos, personagens, relações, localizações \
explicitamente mencionadas, acontecimentos sobrenaturais, ensinamentos, \
falas essenciais, a sequência dos acontecimentos ou o resultado deles. \
Não invente acontecimentos que contradigam a leitura. Não faça \
personagens dizerem ou fazerem coisas incompatíveis com a Escritura. Não \
transforme uma hipótese narrativa em fato bíblico.

AMBIENTAÇÃO
Pode desenvolver livremente arquitetura, iluminação, clima, sons, \
paisagem, objetos, movimentação de pessoas e atmosfera quando o texto \
bíblico não fornecer todos os detalhes — sempre plausível para o período \
bíblico. Quando a Escritura indicar explicitamente onde um acontecimento \
ocorre (templo, casa, sinagoga, cidade, estrada, mar, monte, deserto \
etc.), esse local deve ser respeitado — nunca troque por outro só para \
tornar a cena mais dramática. Quando o ambiente não for especificado, \
crie um cenário hipotético plausível, sem apresentá-lo como fato bíblico.

CONTEXTO HISTÓRICO
Respeite costumes, arquitetura, vestimentas, alimentação, objetos, meios \
de transporte, práticas religiosas e geografia da época. Nunca insira \
elementos modernos (carros, eletrônicos, roupas ou tecnologia \
contemporânea).

PERSONAGENS
Utilize os personagens da leitura. Quando uma Bíblia Visual dos \
Personagens for fornecida, respeite rigorosamente suas características \
(idade, aparência, rosto, cabelo, olhos, barba, corpo, roupas) — não as \
altere.

ESTRUTURA POR CENA
Organize o roteiro em cenas, cada uma EXATAMENTE neste formato (mantenha \
esses rótulos e essa pontuação, para permitir processamento automático):

CENA 1 — Título descritivo da cena
Local:
[local]
Momento:
[período do dia, quando pertinente]
Narração:
[texto completo que será narrado, natural para locução]

CENA 2 — Título descritivo da cena
Local:
...

Continue numerando sequencialmente (CENA 1, CENA 2, CENA 3, ...) até o \
fim do roteiro.

MOMENTOS SOBRENATURAIS
Anjos, milagres, visões e revelações devem ser narrados de forma \
grandiosa, solene e cinematográfica — majestade, reverência, mistério, \
sem banalizar.

TOM
Solene, envolvente, cinematográfico, contemplativo, emocional, \
reverente e acessível. Evite linguagem acadêmica demais, coloquial \
demais ou melodramática.

ESTRUTURA NARRATIVA (quando a passagem permitir)
Introdução, contexto, apresentação dos personagens, estabelecimento do \
local, desenvolvimento dos acontecimentos, momento central da leitura, \
clímax, consequência, encerramento e uma breve reflexão final coerente \
com a passagem — sem forçar essa estrutura quando não for adequada, e \
sem transformar a reflexão em um sermão longo.

ABERTURA E ENCERRAMENTO DO VÍDEO
O roteiro é narração de um vídeo, não só um texto lido — por isso \
precisa de uma abertura breve e um encerramento breve, além da \
introdução/reflexão narrativas descritas acima. As frases de saudação \
inicial e de agradecimento final são FIXAS e inseridas automaticamente \
pelo sistema (não pela IA) — a Narração da CENA 1 sempre vai começar, \
já pronto, com "Bem-vindo, querido espectador." e a Narração da ÚLTIMA \
cena sempre vai terminar, já pronto, com "Obrigado pela sua companhia." \
Por isso:
- NÃO escreva nenhuma saudação própria ("bem-vindo", "olá", "seja \
  bem-vindo" etc.) no início da CENA 1 — comece direto pelo conteúdo \
  descrito no próximo item, que será colado logo depois da saudação fixa.
- No início da Narração da CENA 1, escreva de 1 a 3 frases curtas \
  preparando o clima para a leitura que vem a seguir (ex.: convidar a se \
  acomodar, silenciar o celular, mergulhar na história), antes de \
  começar a contar a história em si. Mesmo tom solene e reverente do \
  restante do roteiro — nunca comercial, apressado ou fora do clima \
  bíblico. Não invente nome de canal, autor ou qualquer identificação \
  que não foi fornecida.
- NÃO escreva nenhum agradecimento/despedida própria ("obrigado por \
  assistir", "até a próxima" etc.) no final da última cena — termine seu \
  texto no convite descrito no próximo item; o agradecimento fixo será \
  colado logo depois.
- No final da Narração da ÚLTIMA cena, depois da reflexão final, \
  acrescente de 2 a 4 frases curtas de encerramento convidando o \
  espectador a curtir o vídeo, se inscrever no canal, compartilhar com \
  alguém que também gostaria de ouvir essa história, e deixar um \
  comentário (pode ser um convite específico relacionado à passagem, \
  ex.: pedir para contar nos comentários o que a mensagem significou \
  para essa pessoa). Mesmo tom solene do resto do roteiro — nunca soe \
  como propaganda.
- Essas frases de abertura/encerramento fazem parte do texto que será \
  narrado (contam para a duração total) — não são um bloco separado, \
  não levam rótulo próprio, e não aparecem em nenhuma outra cena além \
  da primeira e da última.

DURAÇÃO
Aproximadamente 2.400 a 3.000 palavras no total. Não prolongue \
artificialmente a história só para atingir a quantidade — quando a \
passagem for curta, desenvolva ambientação, contexto, transições e \
emoções presentes no próprio texto, nunca acontecimentos novos.

SAÍDA
Entregue SOMENTE o roteiro, já dividido em cenas no formato acima \
(incluindo a abertura dentro da Narração da CENA 1 e o encerramento \
dentro da Narração da última cena, como descrito acima). Não inclua \
análise da passagem, explicações, comentários técnicos, prompts de \
imagem ou instruções para o narrador.\
"""


def build_narration_user_message(
    *, bible_reference: str, passage_text: str, biblia_visual_text: str | None
) -> str:
    parts = [
        f"REFERÊNCIA BÍBLICA:\n{bible_reference}",
        f"TEXTO COMPLETO DA LEITURA:\n{passage_text}",
    ]
    if biblia_visual_text and biblia_visual_text.strip():
        parts.append(f"BÍBLIA VISUAL DOS PERSONAGENS (respeitar rigorosamente):\n{biblia_visual_text}")
    parts.append("Gere o roteiro completo seguindo todas as regras do sistema.")
    return "\n\n".join(parts)


SCENE_EXTRACTION_SYSTEM_PROMPT = """\
Você recebe uma lista de cenas de um roteiro de narração bíblica, cada \
uma já com local, momento e o texto de narração. Sua única tarefa é \
devolver, para CADA cena (identificada pelo campo "order"), estes campos \
adicionais:

- "characters": lista dos nomes dos personagens presentes na cena (a \
  partir do texto da narração e, se fornecida, da Bíblia Visual);
- "action": um resumo curto (1 frase) do que está acontecendo na cena;
- "emotion": a emoção dominante da cena (1-3 palavras, ex.: "tensão", \
  "alívio", "reverência");
- "visual_importance": "low", "medium" ou "high" — quão central essa \
  cena é para a compreensão visual da história.

NÃO repita o texto da narração, local ou momento — eles já existem e \
não devem ser alterados.

Responda APENAS com um array JSON válido, sem markdown, sem comentários, \
sem texto antes ou depois. Formato exato:

[{"order": 1, "characters": ["Nome"], "action": "...", "emotion": "...", "visual_importance": "medium"}]\
"""


def build_scene_extraction_user_message(
    *, raw_scenes: list[dict], biblia_visual_text: str | None
) -> str:
    payload = [
        {
            "order": scene["order"],
            "location": scene["location"],
            "time": scene["time"],
            "narration": scene["narration"],
        }
        for scene in raw_scenes
    ]
    parts = [f"CENAS:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"]
    if biblia_visual_text and biblia_visual_text.strip():
        parts.append(f"BÍBLIA VISUAL DOS PERSONAGENS:\n{biblia_visual_text}")
    return "\n\n".join(parts)
