PASSAGEM BÍBLICA
       │
       ▼
┌──────────────────────────┐
│ 1. GERADOR DE NARRAÇÃO   │
│                          │
│ Bíblia + regras          │
│ + Bíblia Visual          │
└────────────┬─────────────┘
             │
             ├──► roteiro_narracao.md
             │
             ▼
┌──────────────────────────┐
│ 2. GERADOR DE ÁUDIO      │
│                          │
│ Texto → TTS local        │
└────────────┬─────────────┘
             │
             └──► narracao.mp3           
             │
             ▼
┌──────────────────────────┐
│ 3. GERADOR DE IMAGENS    │
│                          │
│ Roteiro + Bíblia Visual  │
│ + regras de continuidade│
└────────────┬─────────────┘
             │
             └──► prompts_imagens.txt
                         │
                         ▼
                    META AUTOMATION
                         │
                         └──► imagens/
                              001.png
                              002.png
                              003.png
                              ...

             │
             ▼
┌──────────────────────────┐
│ 4. GERADOR DE VÍDEOS     │
│                          │
│ Cada imagem + contexto   │
│ da cena                   │
└────────────┬─────────────┘
             │
             └──► prompts_videos.txt
                         │
                         ▼
                    VIBES AUTOMATION
                         │
                         └──► videos/
                              001.mp4
                              002.mp4
                              003.mp4

             │
             ▼
┌──────────────────────────┐
│ 5. MONTADOR AUTOMÁTICO   │
│                          │
│ MP3 + vídeos + cenas     │
│ + duração da narração    │
└────────────┬─────────────┘
             │
             ▼
             video_base.mp4
             │
             ▼
        KDENLIVE / CAPCUT
        (acabamento final)