from django import template
from django.db.models import Manager
from django.urls import reverse
from django.utils.html import format_html

from ..permissions import usuario_pode

register = template.Library()


@register.filter
def can(user, permissao):
    """{% if user|can:'ver_alunos' %} ... {% endif %}"""
    return usuario_pode(user, permissao)


@register.filter
def campo(form, nome):
    """Acessa um campo do formulário pelo nome: {{ form|campo:'nome' }}"""
    return form[nome]


@register.filter
def valor(objeto, caminho):
    """
    Lê um atributo (aceita caminho com pontos, métodos e propriedades) e o
    formata para exibição: {{ aluno|valor:'user.nome_exibicao' }}
    """
    atual = objeto
    for parte in caminho.split("."):
        if atual is None:
            return "—"
        try:
            atual = getattr(atual, parte)
        except Exception:
            return "—"
        eh_manager = isinstance(atual, Manager) or getattr(atual, "do_not_call_in_templates", False)
        if callable(atual) and not eh_manager:
            atual = atual()

    if atual is None or atual == "":
        return "—"
    if isinstance(atual, bool):
        return "Sim" if atual else "Não"
    if isinstance(atual, str) and atual.startswith(("http://", "https://")):
        return format_html('<a href="{0}" target="_blank" rel="noopener">{0}</a>', atual)
    return atual


@register.simple_tag
def rota(prefixo, acao, pk=None):
    """{% rota 'aluno' 'update' obj.pk as url %} -> reverse('aluno_update', args=[pk])"""
    nome = f"{prefixo}_{acao}"
    return reverse(nome, args=[pk]) if pk is not None else reverse(nome)
