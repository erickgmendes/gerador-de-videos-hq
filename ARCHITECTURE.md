# Arquitetura

## Camadas

```
Navegador (HTML + HTMX + Alpine.js, vendorizados em static/vendor — sem build step)
        │  HTTP
FastAPI — rotas finas (app/web/routes, app/api/v1)
        │
Application Services (app/services) — regra de negócio, não conhece FFmpeg/TTS/YouTube
        │
Domain / Core (app/domain) — entidades e enums de estado, zero dependência de framework
        │
Ports (typing.Protocol em app/adapters/*/base.py)
        │
Adapters (implementações concretas — chegam junto com cada fase que as usa)
```

Repositórios (`app/repositories`, SQLAlchemy) e storage de arquivos
(`app/storage/project_storage.py`) ficam na camada de infraestrutura,
acessados pelos services — nunca diretamente pelas rotas.

## Stack

- **Backend**: Python 3.11+, FastAPI + Uvicorn.
- **Frontend**: Jinja2 + HTMX + Alpine.js (vendorizados localmente, sem
  CDN em runtime, sem Node/build step) + CSS próprio em `static/css/app.css`.
- **Banco**: SQLite via SQLAlchemy 2.0 + Alembic, preparado para migrar
  para PostgreSQL no futuro (basta trocar `DATABASE_URL`).
- **Config**: pydantic-settings lendo `.env` (segredos) — ver `app/config.py`.
- **Processamento assíncrono** (a partir da Fase 2): `BackgroundTasks` do
  FastAPI + tabela `jobs` (progresso/erro), sem Celery/Redis —
  desnecessário para um app local de usuário único. Jobs que ficam
  "running" porque o processo foi encerrado no meio são reconciliados
  (marcados como falha) no `lifespan` de `app/main.py`.
- **IA/LLM** (Fase 2): Groq (GroqCloud) é a IA principal, via API
  compatível com OpenAI (`app/adapters/ai/groq_adapter.py`, usa o pacote
  `openai` apontado para `https://api.groq.com/openai/v1`). Chave em
  `GROQ_API_KEY`, modelo em `GROQ_MODEL` (padrão `openai/gpt-oss-120b`)
  — gratuita, sem cartão de crédito; escolha do usuário, não
  Anthropic/Claude nem xAI/Grok (fácil de confundir "Groq" com "Grok" —
  são empresas diferentes). O padrão original era `groq/compound`
  (escolhido pelo teto de 70K tokens/min no tier gratuito, bem maior que
  o resto); a Groq descontinuou esse modelo em 21/09/2026 (chamadas a ele
  passaram a devolver 404) e reduziu TODOS os modelos restantes do tier
  gratuito a um teto de 8K TPM — ver nota na seção "Limite de
  tokens/minuto" abaixo, que hoje descreve uma limitação permanente, não
  mais contornável trocando de modelo dentro da Groq.
- **IA/LLM — backup automático** (`app/adapters/ai/gemini_adapter.py`):
  Google Gemini, também via API compatível com OpenAI
  (`https://generativelanguage.googleapis.com/v1beta/openai/`). Chave em
  `GEMINI_API_KEY`, modelo em `GEMINI_MODEL` (padrão `gemini-3.8-flash`)
  — gratuito, sem cartão de crédito. `app/adapters/ai/get_ai_adapter()`
  (`app/adapters/ai/__init__.py`) decide o que devolver: se as duas
  chaves estiverem configuradas, envolve as duas num
  `FallbackAIAdapter` (`app/adapters/ai/fallback_adapter.py`) — tenta a
  Groq primeiro e só chama o Gemini se a Groq levantar `AIProviderError`
  (chave ausente, limite de uso, erro de rede etc.); com só uma das duas
  configuradas, usa aquela sozinha; sem nenhuma, levanta erro amigável.
  Motivado por um caso real: o tier gratuito da Groq tem um teto diário
  de requisições, e a geração de prompts de imagem de um projeto com
  muitas cenas pode esgotá-lo no meio do processo. `GeminiAdapter` é um
  arquivo próprio (não compartilha base com `GroqAdapter`) deliberadamente
  — mesma filosofia de retry, mas isolado para não arriscar o adapter da
  Groq, que já estava em produção quando o backup foi criado.
- **Gerenciamento de chaves** (`app/services/settings_service.py`): a
  tela Configurações permite colar/atualizar cada chave direto pela UI —
  grava no `.env` local (nunca no banco, nunca em log) e limpa o cache de
  `get_settings()`, valendo imediatamente sem reiniciar. `_SECRET_FIELD_DEFS`
  é o registro único de quais chaves aparecem ali; uma integração nova
  (YouTube etc.) só precisa de uma entrada nova + uma rota de formulário.
  Único módulo autorizado a escrever no `.env`.
- **TTS** (Fase 3): `edge-tts` (`app/adapters/tts/edge_tts_adapter.py`) —
  vozes de nuvem do Microsoft Edge, gratuitas, sem chave, mas exigem
  internet. Voz/velocidade em `TTS_VOICE`/`TTS_RATE` (padrão
  `pt-BR-AntonioNeural` / `-4%`).
- **FFmpeg** (Fase 3+): binário portátil via `imageio-ffmpeg` (já
  empacotado, sem instalação manual) — `app/adapters/ffmpeg/ffmpeg_adapter.py`.
  Duração de áudio lida com `mutagen` (a lib não empacota `ffprobe`).
- **Imagens** (Fase 4): sem adapter novo — reaproveita `AIProviderAdapter`
  (Groq) para gerar as descrições; sem serviço de imagem em si (a geração
  da imagem a partir do prompt é externa — Meta Automation).

## Estrutura de diretórios

```
app/
├── main.py                # app factory
├── config.py               # Settings (pydantic-settings)
├── db.py                    # engine/session, Base declarativa
├── domain/                  # entidades e máquina de estados — puro Python
├── services/                # regra de negócio (um pacote por etapa do pipeline)
├── adapters/                # portas (Protocol) para IA/TTS/FFmpeg/YouTube
├── repositories/             # acesso a dados via SQLAlchemy
├── models/orm.py              # modelos SQLAlchemy
├── schemas/                   # DTOs Pydantic
├── storage/project_storage.py  # único módulo que monta caminhos dentro de PROJECTS_DIR
├── diagnostics/checks.py       # verificações de ambiente
├── web/                        # rotas HTML (Jinja2 + HTMX) e templates
└── api/v1/                     # rotas JSON mínimas (health, futura automação)
alembic/                # migrações do banco
static/{css,vendor}/    # CSS próprio + htmx.js/alpine.min.js vendorizados
projects/                # dados reais dos projetos (gitignored)
data/app.db               # SQLite (gitignored)
tests/{unit,integration}/
```

Cada projeto em `projects/<id>/` segue:
`input/`, `roteiro/`, `audio/`, `prompts/`, `images/`, `videos/`, `output/`,
`metadata/` (+ `metadata/logs/`). `id` é um slug (nome + data + sufixo
curto) — usado como chave primária e como nome da pasta, mantendo o
projeto inteiro portátil/movível.

## Modelo de dados

- **projects** — id (slug), nome, referência bíblica, `state` (estágio
  macro do pipeline), timestamps, status do YouTube.
- **scenes** — cenas do roteiro (espelha `roteiro/cenas.json`).
- **characters** — cache indexado de um bloco do
  `biblia-visual-personagens.md` do projeto (o `.md` continua sendo a
  fonte canônica; a tabela só existe para detectar personagens ausentes).
- **artifacts** — metadados de qualquer arquivo gerado/enviado (narração,
  áudio, imagem, vídeo, prompt, vídeo final) — nunca o binário em si.
- **jobs** — rastreia operações assíncronas longas (Fase 2+); existe desde
  a Fase 1 como infraestrutura de retomada.
- **image_prompts** (Fase 4, primeira migração desde a Fase 1) — um
  painel de quadrinho (não uma cena): `scene_id`, `global_order` (001,
  002... no projeto inteiro, bate com o nome dos arquivos enviados),
  `order_in_scene`, `shot_type`, `prompt_text`, `image_path` (após
  upload).
- **assembly_configs**, **youtube_publications**, **app_settings** —
  schema já criado, populados de fato a partir das Fases 6/8.

`roteiro/cenas.json` (a partir da Fase 2) é a estrutura de trabalho
legível por humano/IA; a tabela `scenes` é o índice consultável pela
aplicação — os dois são escritos juntos pelo serviço de roteiro.

### Geração da narração (Fase 2)

`app/services/narration/service.py` orquestra três passos:

1. **IA** (`GroqAdapter.complete`) gera o roteiro completo no formato
   `CENA N — Título / Local: / Momento: / Narração:`, salvo em
   `roteiro/narracao.md` **antes** de qualquer parsing — nada se perde
   mesmo se a extração de cenas falhar depois.
2. **Parsing determinístico**, sem IA (`scene_parser.py`): divide o
   texto em cenas por regex, extraindo local/momento/narração
   literalmente (o texto da narração nunca é reescrito por uma segunda
   chamada de IA — é o que a Fase 3 vai sintetizar em áudio) e calcula
   `estimated_duration` por contagem de palavras.
3. **IA de novo**, só para enriquecer cada cena com `characters`,
   `action`, `emotion`, `visual_importance` (JSON), sem repetir a
   narração — economiza tokens e evita deriva do texto.

O resultado grava `roteiro/cenas.json` e substitui as linhas de `scenes`
no banco. Erros em qualquer etapa marcam o `Job` como falho com mensagem
amigável e revertem `Project.state` para `CREATED`, sem apagar um
`narracao.md` já salvo.

**`roteiro/texto_narracao.txt`**: além do `narracao.md` estruturado (com
`CENA N — Título / Local: / Momento:`), o serviço também grava, via
`build_flowing_text(scenes)`, só o texto narrado — corrido, na ordem das
cenas, sem nenhum rótulo. Motivo: um narrador humano não deve ler "CENA
3, Local: ..." em voz alta (feedback do usuário testando a Fase 2), e a
Fase 3 (TTS) vai sintetizar exatamente este texto, não o `.md` bruto.
Reconstruído a partir de `scenes` sob demanda (não só do arquivo) para
projetos antigos gerados antes dessa mudança continuarem funcionando.

**Limite de tokens/minuto do tier gratuito da Groq**: testado ao vivo
durante o desenvolvimento — os modelos `openai/gpt-oss-*` e `qwen/*`
compartilham um teto de 8K TPM no tier gratuito, insuficiente até para
uma única narração completa (uma narração de ~2.700 palavras já consome
uns 10-12K tokens contando o "raciocínio" interno desses modelos de
reasoning). O modelo padrão original driblava isso usando `groq/compound`
(teto de 8192 em `max_tokens` por chamada, mas 70K TPM) — cabia a
narração inteira numa chamada e ainda sobrava orçamento para a chamada
de enriquecimento logo em seguida. A Groq descontinuou `groq/compound`
em 21/09/2026; **não existe mais nenhum modelo no tier gratuito da Groq
com teto acima de 8K TPM** — ou seja, o problema que motivou a escolha
do `compound` voltou a existir, sem alternativa dentro da própria Groq.
Isso também afeta a Fase 4 (prompts de imagem): cada chamada por cena
inclui o texto inteiro da Bíblia Visual do projeto, que facilmente passa
de 8K tokens sozinho. Por isso o backup via `GEMINI_API_KEY`
(`app/adapters/ai/fallback_adapter.py`, tier gratuito do Gemini gira em
torno de 250K TPM) deixou de ser um "nice-to-have" — sem ele configurado,
Groq sozinha esbarra no limite com frequência tanto na narração quanto
nos prompts de imagem. `GroqAdapter` (`app/adapters/ai/groq_adapter.py`)
ainda tenta de novo automaticamente (até 2 vezes, aguardando ~25s) antes
de reportar erro ou cair para o backup, mas isso amortece picos
pontuais, não substitui ter o Gemini configurado.

### Geração de áudio (Fase 3)

Decisão revista durante o desenvolvimento: o plano original (Fase 2)
previa sintetizar `narracao.md` inteiro de uma vez só. O usuário, ao ver
que cada cena já vem com sua narração isolada, pediu algo melhor para
edição — a mesma resposta que resolve isso também evita depender de uma
única chamada de TTS gigante (mais sujeita a falha):

- **Áudio por cena é o artefato principal** (`audio/scenes/{ordem}.mp3`,
  um `Artifact` tipo `narration_audio_scene` por cena) — editável e
  substituível independentemente, no mesmo padrão que imagens e vídeos já
  usam neste app (Fases 4/5). `Scene.actual_duration` passa a guardar a
  duração real medida (não mais a estimativa por contagem de palavras da
  Fase 2).
- Quando **todas** as cenas do projeto têm áudio, `app/services/audio/service.py`
  concatena tudo com `FFmpegAdapter.concat_audio` num arquivo único
  (`audio/narracao.mp3`, `Artifact` tipo `narration_audio`) — com filtro
  `loudnorm` (EBU R128, alvo -16 LUFS) para não haver salto de volume nem
  corte perceptível na emenda entre cenas sintetizadas separadamente.
  Regenerar o áudio de uma cena específica automaticamente remescla o
  arquivo final.
- **Bug real encontrado em desenvolvimento**: o encoder `libmp3lame` trava
  (`Assertion failed: el >= 0`) ao aplicar `loudnorm` sobre áudio de
  silêncio digital puro — improvável com fala real do TTS, mas
  `concat_audio` já cai automaticamente para concatenação sem
  normalização se a primeira tentativa falhar, em vez de derrubar a etapa
  inteira.

### Prompts de imagem (Fase 4)

**Uma cena não é uma imagem.** A spec mestra sugeria 1:1 ("24 cenas → 24
imagens"), mas o usuário trouxe a conta real: cenas têm ~26s de áudio
(Fase 3), cada vídeo animado (Fase 5) cobre só ~`VIDEO_SEGMENT_SECONDS`
(padrão 5s) — logo cada cena precisa de vários painéis, calculados por
`compute_panel_count = ceil(actual_duration / VIDEO_SEGMENT_SECONDS)`,
não por "complexidade narrativa". Por isso existe a tabela
`image_prompts`, independente de `scenes` (many-to-one).

`app/services/image_prompts/service.py` — uma chamada de IA **por
cena** (não uma mega-chamada para o projeto inteiro, para não estourar
o limite de tokens/minuto da Fase 2/3 já documentado acima), pedindo
exatamente `panel_count` painéis variando enquadramento. O bloco de
estilo artístico/formato/negative-prompt (~200 palavras, idêntico em
TODO prompt) é **montado pelo código**, não redigitado pela IA a cada
painel — mesma filosofia da Fase 2 (narração vs. extração de cenas).

**Cache de personagens entre cenas** (`characters`, existente desde a
Fase 1, agora finalmente usada): a IA só descreve um personagem na
primeira cena em que ele aparece; da segunda cena em diante, a
descrição salva é reaproveitada literalmente. Sem isso, cada cena sendo
uma chamada de IA independente faria "Jesus" sair descrito de um jeito
na cena 3 e diferente na cena 7.

**Cache de cenários entre cenas** (`locations`, mesmo mecanismo e mesmo
motivo do cache de personagens acima, adicionado depois que o usuário
relatou quebra de continuidade visual entre painéis): a IA reaproveita
literalmente a descrição de um cenário já visto (ex.: "o templo" numa
cena e "o Templo de Jerusalém" noutra são o mesmo lugar físico), em vez
de redescrever arquitetura/iluminação do zero a cada cena que volta ao
mesmo local.

**Continuidade DENTRO da mesma cena**: o cache de personagens/cenários
resolve a consistência *entre* cenas, mas não a de painéis *dentro* da
mesma cena — como uma cena pode ter vários painéis (ver cálculo acima) e
todos vêm da mesma chamada de IA, o `IMAGE_PROMPT_SYSTEM_PROMPT` agora
instrui explicitamente que painéis da mesma cena são frames consecutivos
de um único momento contínuo: roupa e cenário devem se repetir palavra
por palavra entre eles, variando só pose/expressão/enquadramento — a
menos que a ação da própria cena mude a roupa ou o local do personagem.
Isso não resolve inconsistência introduzida pela ferramenta externa de
geração de imagem em si (sem controle de seed/imagem de referência,
texto idêntico ainda pode render diferente) — é um limite conhecido do
fluxo atual (geração de imagem é externa — Meta Automation), não algo
que o prompt sozinho garanta 100%.

**Três bugs reais encontrados testando com o projeto real do usuário**
(18 cenas, não só fixtures pequenas):
1. `recompute_project_state` só olhava se as imagens já tinham sido
   enviadas, não se **todas as cenas** já tinham painéis gerados — uma
   geração parcial (interrompida, ou uma chamada visando só uma cena)
   reportava `IMAGE_PROMPTS_READY` prematuramente. Corrigido para exigir
   cobertura de 100% das cenas antes de sair de `IMAGE_PROMPTS_GENERATING`
   (que agora é tanto "rodando agora" quanto "repouso parcial", mesmo
   padrão que `AUDIO_GENERATING` já era).
2. Consequência do bug 1: o template usava `project.state ==
   'image_prompts_generating'` para decidir se mostrava o spinner com
   polling — como esse estado virou também um "repouso parcial", isso
   criava um polling infinito numa página onde nenhum job está rodando.
   Corrigido para checar `latest_job.status == 'running'` (o sinal
   confiável), não o estado macro.
3. `reconcile_stale_jobs` (recuperação ao reiniciar a aplicação) usava um
   alvo fixo (`AUDIO_READY`) para `image_prompts` — escondia progresso
   real já salvo (painéis gerados com sucesso antes da interrupção).
   Agora chama `recompute_project_state` de verdade para este job_type.

## Fluxo de estados

Duas dimensões deliberadas (ver `app/domain/states.py`):

1. `Project.state` — estágio macro linear do pipeline (dashboard mostra
   este valor como a barra de progresso).
2. Status por etapa/job (`StepStatus`) — onde erros ficam localizados: uma
   falha na montagem não apaga o estado "imagens prontas" de um projeto.

## Multiplataforma

`pathlib.Path` em todo lugar, sem `C:\` ou `/home/` fixos — dados vivem em
`./projects` e `./data`, configuráveis via `.env`. Execução de processos
externos (Fases 3+) sempre via `subprocess.run(args: list[str])`, nunca
`shell=True`. Nenhuma dependência exclusiva de Windows.

## Plano de fases

1. **Fundação** (concluída) — estrutura, backend, frontend, banco, criação
   de projetos, dashboard, persistência, configuração, diagnóstico básico.
   Edição e exclusão de projeto (`ProjectService.update_project`/
   `delete_project`, adicionadas depois, fora do plano de fases original a
   pedido do usuário) nunca mudam `Project.id` — o id é gerado uma vez na
   criação (slug do nome + data + sufixo aleatório) e vira o nome da pasta
   em `./projects` e parte de toda URL do projeto; editar o nome depois
   não renomeia a pasta nem muda links já visitados. Excluir apaga a linha
   do banco (cascata via `cascade="all, delete-orphan"` cuida de cenas,
   jobs, personagens, cenários, prompts de imagem e artifacts) e depois a
   pasta inteira do projeto em disco — nessa ordem, para nunca ficar com
   arquivos órfãos se o passo do banco falhar no meio.
2. **IA: narração + `cenas.json`** (concluída) — geração via Groq,
   parsing determinístico de cenas, enriquecimento estrutural, aba
   Narração com acompanhamento em tempo real e retomada após reinício.
3. **TTS/MP3 + metadados de áudio** (concluída) — síntese por cena via
   edge-tts, concatenação normalizada num arquivo final via FFmpeg,
   regeneração pontual por cena, aba Áudio com players e acompanhamento
   em tempo real.
4. **Prompts de imagem + exportação + upload + associação a cenas**
   (concluída) — cálculo de painéis por duração, cache de personagens,
   exportação `.txt`, upload em lote com associação por nome de arquivo
   e upload individual de correção.
5. Prompts de vídeo + upload + associação a cenas.
6. FFmpeg: sincronização, montagem, transições.
7. Player, revisão por cena, substituição, remontagem.
8. YouTube: autenticação, upload, publicação, registro.
9. Backup/ZIP, documentação final, Docker, preparação Linux/macOS.

Cada fase só começa após a anterior rodar, com testes passando e o fluxo
principal validado manualmente.
