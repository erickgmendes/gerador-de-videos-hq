O painel principal

Eu imaginaria algo mais ou menos assim:

Dashboard
╔════════════════════════════════════════════════════════════╗
║  PRODUÇÃO BÍBLICA                              + NOVO PROJETO║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  PROJETOS EM PRODUÇÃO                                      ║
║                                                            ║
║  Evangelho — 13/09/2026                                   ║
║  ████████████████░░░░  80%                                ║
║                                                            ║
║  ✓ Narração       ✓ Áudio       ✓ Imagens                  ║
║  ✓ Prompts vídeo  ◉ Upload     ○ Montagem                  ║
║                                                            ║
║  [Continuar projeto]                                       ║
║                                                            ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  PROJETOS CONCLUÍDOS                                       ║
║                                                            ║
║  Evangelho — 06/09/2026                  PUBLICADO         ║
║  Evangelho — 30/08/2026                  PUBLICADO         ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
Cada projeto teria seu próprio painel

Ao entrar no projeto:

EVANGELHO — 13/09/2026

[Informações] [Narração] [Áudio] [Imagens] [Vídeos]
[Montagem] [Revisão] [YouTube]

E cada etapa teria seu próprio status.

Por exemplo:

Imagens
GERAÇÃO DE IMAGENS

Total de cenas: 24

✓ 001.png
✓ 002.png
✓ 003.png
✓ 004.png
✓ 005.png
...
○ 024.png

[Copiar todos os prompts]

[Baixar prompts]

Você poderia então levar os prompts para o Meta Automation.

Quando terminar:

arrasta a pasta de imagens para a aplicação.

A aplicação identifica:

001.png
002.png
003.png
...
024.png

e associa automaticamente às cenas.

O mesmo para os vídeos

Essa parte é especialmente importante.

A aplicação poderia mostrar:

VÍDEOS

Cena 001    ✓ video_001.mp4
Cena 002    ✓ video_002.mp4
Cena 003    ✓ video_003.mp4
Cena 004    ⚠ aguardando
Cena 005    ✓ video_005.mp4
Cena 006    ⚠ aguardando

          4 / 6 vídeos recebidos

[Upload vídeos]

E, se o arquivo tiver um padrão de nome, melhor ainda:

001.mp4
002.mp4
003.mp4

A aplicação sabe exatamente onde cada vídeo pertence.

A montagem automática

Aqui temos uma oportunidade muito boa.

O sistema poderia mostrar:

MONTAGEM

Narração
████████████████████████████████████ 20:14

Cena 001 ─── 8.2s
Cena 002 ───── 11.4s
Cena 003 ── 6.8s
Cena 004 ─────── 13.1s
...

[Gerar vídeo]

        ↓

video_final.mp4

E antes de gerar, poderia haver configurações:

Duração padrão das cenas: [Automática ▼]

Transição:
[Crossfade ▼]

Duração:
[0.5] segundos

Fade inicial:     [✓]
Fade final:       [✓]

Áudio da narração: [100%]
Música de fundo:   [Desativada]

[GERAR VÍDEO]
E a tela de revisão é importantíssima

Eu colocaria um player de vídeo diretamente na aplicação:

┌─────────────────────────────────────────────┐
│                                             │
│                                             │
│              ▶ VIDEO FINAL                  │
│                                             │
│                                             │
└─────────────────────────────────────────────┘

00:00 ─────────────────────────────── 20:14

[▶ Reproduzir] [⏸] [🔊]

STATUS: EM REVISÃO

[✓ APROVAR VÍDEO]

[↩ Voltar para montagem]

Mas podemos ir além.

O usuário poderia clicar em uma cena específica e visualizar:

Cena 12

Imagem:
[imagem]

Vídeo:
[player]

Narração:
"Naquele momento..."

Prompt da imagem:
[visualizar]

Prompt do vídeo:
[visualizar]

[Substituir vídeo]
[Regenerar prompt]

Isso seria extremamente útil para detectar rapidamente uma cena problemática.

YouTube

Também é perfeitamente possível integrar isso.

A aplicação poderia ter uma etapa:

PUBLICAÇÃO NO YOUTUBE

Vídeo:
✓ video_final.mp4

Título:
[Evangelho do Dia — 13 de Setembro de 2026]

Descrição:
[................................................]

Tags:
[evangelho, bíblia, oração, ... ]

Thumbnail:
[thumbnail.jpg]

Visibilidade:

○ Privado
○ Não listado
● Público

Categoria:
[Educação ▼]

[ENVIAR PARA O YOUTUBE]

Para isso, a aplicação precisará utilizar a API oficial do YouTube e fazer a autenticação da conta. Essa parte deve ser construída de forma segura, sem colocar tokens ou credenciais diretamente no código.

Uma melhoria que considero ainda mais importante

Eu faria o sistema trabalhar com etapas independentes e retomáveis.

Por exemplo, você gera a narração hoje:

✓ NARRAÇÃO

Amanhã pode abrir o projeto novamente:

✓ NARRAÇÃO
✓ ÁUDIO
○ IMAGENS
○ VÍDEOS
○ MONTAGEM
○ REVISÃO
○ YOUTUBE

E continuar exatamente de onde parou.

Se o computador reiniciar, não importa.

E sobre o Claude Code

Eu não criaria ainda o prompt gigante para ele.

Primeiro devemos definir a arquitetura que queremos que ele implemente.

Eu recomendaria dividir o desenvolvimento em fases:

Fase 1 — Fundação
aplicação web;
dashboard;
criação de projetos;
armazenamento dos projetos;
gerenciamento de arquivos;
estados das etapas.
Fase 2 — IA
geração da narração;
geração do cenas.json;
geração dos prompts de imagens;
geração dos prompts de vídeos.
Fase 3 — Áudio
TTS;
geração local do MP3;
duração;
sincronização.
Fase 4 — Importação
upload das imagens;
upload dos vídeos;
associação automática com as cenas;
validação de arquivos faltantes.
Fase 5 — Montagem
FFmpeg;
sincronização com narração;
timeline;
transições;
geração do MP4.
Fase 6 — Revisão
player;
revisão por cena;
substituição de vídeos;
regeneração da montagem.
Fase 7 — YouTube
autenticação;
título;
descrição;
tags;
thumbnail;
publicação;
privado/não listado/público;
registro do ID e URL do vídeo publicado.
E existe uma decisão arquitetural que precisamos tomar antes do prompt

Como você pretende usar isso provavelmente no seu computador, eu faria inicialmente uma aplicação web local:

Seu computador
      │
      ▼
┌─────────────────────┐
│ Aplicação Web       │
│ localhost:xxxx      │
├─────────────────────┤
│ Python              │
│ Banco de dados      │
│ FFmpeg              │
│ TTS                 │
│ Gerenciamento       │
└─────────────────────┘
      │
      ├── Meta Automation
      ├── Vibes Automation
      └── YouTube API

Você abre no navegador:

http://localhost:xxxx

Não precisa de servidor externo inicialmente.

E isso combina muito bem com seu objetivo de reduzir custos.

Depois, se o projeto ficar maduro, podemos transformar a aplicação em algo que rode em um VPS ou servidor doméstico.