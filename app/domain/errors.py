class DomainError(Exception):
    """Erro de regra de negócio — deve virar uma resposta amigável na UI."""


class ProjectNotFoundError(DomainError):
    def __init__(self, project_id: str) -> None:
        super().__init__(f"Projeto '{project_id}' não encontrado.")
        self.project_id = project_id


class ValidationError(DomainError):
    """Dados de entrada inválidos, com uma mensagem já pronta para o usuário."""


class AIProviderError(DomainError):
    """Falha ao chamar o provedor de IA (chave ausente, rede, limite de uso,
    resposta inesperada) — mensagem já amigável para exibir na UI."""


class NarrationParsingError(DomainError):
    """A saída da IA não pôde ser interpretada como cenas (formato inesperado)."""


class TTSError(DomainError):
    """Falha ao sintetizar áudio (rede, serviço de voz indisponível, texto
    vazio) — mensagem já amigável para exibir na UI."""


class AudioAssemblyError(DomainError):
    """Falha ao concatenar/processar os áudios das cenas com o FFmpeg."""


class ImagePromptError(DomainError):
    """A saída da IA não pôde ser interpretada como painéis de imagem
    (formato inesperado), ou faltam pré-requisitos (áudio ainda não
    gerado) para calcular quantos painéis cada cena precisa."""


class VideoPromptError(DomainError):
    """Falta um pré-requisito (nem todos os painéis têm imagem enviada
    ainda) para gerar os prompts de animação — mensagem já amigável para
    exibir na UI. Diferente de ImagePromptError, nunca é sobre uma IA
    (Fase 5 não usa IA — ver app/services/video_prompts/prompts.py)."""
