"""
Perfis (papéis) e permissões do Pro Gym.

Segue a ideia do `roles.py` do Odisseu: cada perfil possui um conjunto de
permissões nomeadas, verificadas pelas views (mixins) e pelos templates
(filtro `can`).
"""

PERMISSOES = {
    # alunos
    "ver_alunos",
    "gerenciar_alunos",
    "excluir_alunos",
    # treinadores
    "ver_treinadores",
    "gerenciar_treinadores",
    # academias
    "ver_academias",
    "gerenciar_academias",
    # matrículas
    "ver_matriculas",
    "gerenciar_matriculas",
    # exercícios
    "ver_exercicios",
    "gerenciar_exercicios",
    # treinos
    "ver_treinos",
    "gerenciar_treinos",
    # avaliações físicas
    "ver_avaliacoes",
    "gerenciar_avaliacoes",
    # dietas
    "ver_dietas",
    "gerenciar_dietas",
    # avaliação do treinador
    "avaliar_treinador",
    "ver_avaliacoes_treinador",
    "gerenciar_avaliacoes_treinador",
    # troca de treinador
    "solicitar_troca",
    "ver_trocas",
    "responder_trocas",
}

# Ações que só fazem sentido para quem é aluno/cliente (o administrador não as executa).
ACOES_DO_ALUNO = {"avaliar_treinador", "solicitar_troca"}

PAPEIS = {
    "administrador": set(PERMISSOES) - ACOES_DO_ALUNO,
    "treinador": {
        "ver_alunos",
        "gerenciar_alunos",
        "ver_academias",
        "ver_exercicios",
        "gerenciar_exercicios",
        "ver_treinos",
        "gerenciar_treinos",
        "ver_avaliacoes",
        "gerenciar_avaliacoes",
        "ver_dietas",
        "gerenciar_dietas",
        "ver_avaliacoes_treinador",
        "ver_trocas",
    },
    "aluno": {
        "ver_academias",
        "ver_matriculas",
        "ver_exercicios",
        "ver_treinos",
        "ver_avaliacoes",
        "ver_dietas",
        "avaliar_treinador",
        "ver_avaliacoes_treinador",
        "solicitar_troca",
        "ver_trocas",
    },
}


def usuario_pode(user, permissao):
    """True se o usuário autenticado possui a permissão informada."""
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return permissao in PAPEIS.get(user.tipo, set())
