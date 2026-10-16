from functools import wraps

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import (
    AcademiaForm,
    AlunoForm,
    AvaliacaoFisicaForm,
    AvaliacaoTreinadorForm,
    CadastroForm,
    DietaForm,
    ExercicioForm,
    MatriculaForm,
    MeuPerfilAlunoForm,
    MeuPerfilTreinadorForm,
    MeuUsuarioForm,
    RefeicaoForm,
    RegistroTreinoForm,
    RespostaTrocaForm,
    SolicitacaoTrocaForm,
    TreinadorForm,
    TreinoForm,
)
from .models import (
    Academia,
    Aluno,
    AvaliacaoFisica,
    AvaliacaoTreinador,
    Dieta,
    Exercicio,
    Matricula,
    Refeicao,
    RegistroTreino,
    SolicitacaoTroca,
    Treinador,
    Treino,
)
from .permissions import usuario_pode


def treinos_visiveis(user):
    if user.is_administrador:
        return Treino.objects.all()
    if user.is_treinador and user.perfil_treinador:
        return Treino.objects.filter(treinador=user.perfil_treinador)
    if user.is_aluno and user.perfil_aluno:
        return Treino.objects.filter(aluno=user.perfil_aluno)
    return Treino.objects.none()


def treinos_gerenciaveis(user):
    if user.is_administrador:
        return Treino.objects.all()
    if user.is_treinador and user.perfil_treinador:
        return Treino.objects.filter(treinador=user.perfil_treinador)
    return Treino.objects.none()


def somente_do_aluno(queryset, user):
    if user.is_aluno and not user.is_administrador:
        perfil = user.perfil_aluno
        return queryset.filter(aluno=perfil) if perfil else queryset.none()
    return queryset


def permissao_requerida(permissao):
    def decorador(view):
        @wraps(view)
        def interna(request, *args, **kwargs):
            if not usuario_pode(request.user, permissao):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return login_required(interna)

    return decorador


class PermissaoMixin(LoginRequiredMixin, UserPassesTestMixin):
    permissao = None

    def test_func(self):
        return self.permissao is None or usuario_pode(self.request.user, self.permissao)


class CrudMixin(PermissaoMixin):
    prefixo = ""  # prefixo dos nomes de URL, ex.: "aluno" -> aluno_list
    singular = ""
    plural = ""
    perm_gerenciar = None
    perm_excluir = None
    # Opções para telas que não têm todas as ações padrão (ex.: trocas, avaliações)
    tem_detalhe = True  # a lista mostra o botão "ver detalhes"
    permite_criar = True  # a lista mostra o botão "novo"
    permite_editar = True  # a lista mostra o botão "editar"
    rotulo_novo = ""  # texto do botão "novo"
    titulo_novo = ""  # título do formulário de criação

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        usuario = self.request.user
        pode_gerenciar = bool(self.perm_gerenciar and usuario_pode(usuario, self.perm_gerenciar))
        contexto.update(
            prefixo=self.prefixo,
            singular=self.singular,
            plural=self.plural,
            pode_gerenciar=pode_gerenciar,
            pode_excluir=bool(self.perm_excluir and usuario_pode(usuario, self.perm_excluir)),
            pode_criar=pode_gerenciar and self.permite_criar,
            linhas_editaveis=pode_gerenciar and self.permite_editar,
            tem_detalhe=self.tem_detalhe,
            rotulo_novo=self.rotulo_novo or f"Novo(a) {self.singular}",
            voltar_url=self.get_voltar_url(),
        )
        return contexto

    def get_voltar_url(self):
        return reverse(f"{self.prefixo}_list")

    def escopo(self, queryset):
        return queryset


class ListaBase(CrudMixin, ListView):
    template_name = "progym/crud/lista.html"
    paginate_by = 10
    colunas = []  # [(rótulo, "caminho.do.atributo")]
    campos_busca = []
    select_related = ()
    texto_busca = "Buscar"

    def get_queryset(self):
        queryset = self.escopo(super().get_queryset())
        if self.select_related:
            queryset = queryset.select_related(*self.select_related)
        busca = self.request.GET.get("q", "").strip()
        if busca and self.campos_busca:
            filtro = Q()
            for campo in self.campos_busca:
                filtro |= Q(**{f"{campo}__icontains": busca})
            queryset = queryset.filter(filtro)
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        busca = self.request.GET.get("q", "").strip()
        contexto.update(
            colunas=self.colunas,
            busca=busca,
            busca_habilitada=bool(self.campos_busca),
            texto_busca=self.texto_busca,
            qs_extra=("&" + urlencode({"q": busca})) if busca else "",
        )
        return contexto


class DetalheBase(CrudMixin, DetailView):
    template_name = "progym/crud/detalhe.html"
    secoes = []  # [(título, [(rótulo, "caminho")])]
    select_related = ()

    def get_queryset(self):
        queryset = self.escopo(super().get_queryset())
        if self.select_related:
            queryset = queryset.select_related(*self.select_related)
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["secoes"] = self.secoes
        return contexto


class FormularioBase(SuccessMessageMixin, CrudMixin):
    """Comportamento comum de criação e edição."""

    template_name = "progym/crud/form.html"
    fieldsets = None  # [(título, [nomes dos campos])]; None = todos os campos

    def get_queryset(self):
        return self.escopo(super().get_queryset())

    def get_success_url(self):
        return reverse(f"{self.prefixo}_list")

    def get_fieldsets(self, form):
        if self.fieldsets:
            return [
                (titulo, [nome for nome in nomes if nome in form.fields])
                for titulo, nomes in self.fieldsets
            ]
        return [(None, list(form.fields))]

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        editando = getattr(self, "object", None) is not None
        contexto.update(
            editando=editando,
            fieldsets=self.get_fieldsets(contexto["form"]),
            titulo_pagina=f"Editar {self.singular}" if editando else (self.titulo_novo or f"Novo(a) {self.singular}"),
        )
        return contexto


class CriarBase(FormularioBase, CreateView):
    pass


class EditarBase(FormularioBase, UpdateView):
    pass


class ExcluirBase(CrudMixin, DeleteView):
    template_name = "progym/crud/confirmar_exclusao.html"
    aviso = ""

    def get_queryset(self):
        return self.escopo(super().get_queryset())

    def get_success_url(self):
        return reverse(f"{self.prefixo}_list")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["aviso"] = self.aviso
        return contexto

    def form_valid(self, form):
        nome = str(self.object)
        resposta = super().form_valid(form)
        messages.success(self.request, f'{self.singular.capitalize()} "{nome}" excluído(a) com sucesso.')
        return resposta


def _nota_media(treinador):
    media = treinador.avaliacoes_recebidas.aggregate(media=Avg("nota"))["media"]
    return f"{media:.1f}".replace(".", ",") if media is not None else "—"


# ===========================================================================
# Painel inicial
# ===========================================================================
@login_required
def index(request):
    usuario = request.user
    hoje = timezone.localdate()
    contexto = {}

    if usuario.is_aluno and not usuario.is_administrador:
        aluno = usuario.perfil_aluno
        if aluno:
            contexto.update(
                aluno=aluno,
                treino_atual=Treino.objects.filter(aluno=aluno)
                .select_related("treinador__user")
                .prefetch_related("registros__exercicio")
                .first(),
                dieta_atual=Dieta.objects.filter(aluno=aluno)
                .select_related("treinador__user")
                .prefetch_related("refeicoes")
                .first(),
                total_treinos=Treino.objects.filter(aluno=aluno).count(),
                ultima_avaliacao=AvaliacaoFisica.objects.filter(aluno=aluno).first(),
                matricula=Matricula.objects.filter(aluno=aluno, ativa=True, data_fim__gte=hoje)
                .select_related("academia")
                .first(),
            )
    else:
        cartoes = []
        if usuario.is_administrador:
            cartoes = [
                ("Alunos", Aluno.objects.count(), "aluno_list", "bi-people"),
                ("Treinadores", Treinador.objects.count(), "treinador_list", "bi-person-badge"),
                (
                    "Matrículas ativas",
                    Matricula.objects.filter(ativa=True, data_fim__gte=hoje).count(),
                    "matricula_list",
                    "bi-card-checklist",
                ),
                ("Treinos", Treino.objects.count(), "treino_list", "bi-clipboard2-pulse"),
                ("Exercícios", Exercicio.objects.count(), "exercicio_list", "bi-lightning-charge"),
                ("Academias", Academia.objects.count(), "academia_list", "bi-building"),
                ("Dietas", Dieta.objects.count(), "dieta_list", "bi-egg-fried"),
                (
                    "Trocas pendentes",
                    SolicitacaoTroca.objects.filter(status=SolicitacaoTroca.PENDENTE).count(),
                    "troca_list",
                    "bi-arrow-left-right",
                ),
            ]
        elif usuario.perfil_treinador:
            treinador = usuario.perfil_treinador
            cartoes = [
                ("Alunos cadastrados", Aluno.objects.count(), "aluno_list", "bi-people"),
                ("Meus treinos", Treino.objects.filter(treinador=treinador).count(), "treino_list", "bi-clipboard2-pulse"),
                ("Avaliações físicas", AvaliacaoFisica.objects.count(), "avaliacao_list", "bi-speedometer2"),
                ("Exercícios", Exercicio.objects.count(), "exercicio_list", "bi-lightning-charge"),
                ("Minhas dietas", Dieta.objects.filter(treinador=treinador).count(), "dieta_list", "bi-egg-fried"),
                ("Minha nota média", _nota_media(treinador), "avaliacao_treinador_list", "bi-star"),
            ]
        contexto["cartoes"] = cartoes

    return render(request, "progym/index.html", contexto)



def cadastro(request):
    """Auto-cadastro público: cria um usuário do tipo aluno e já o autentica."""
    if request.user.is_authenticated:
        return redirect("index")

    if request.method == "POST":
        form = CadastroForm(request.POST)
        if form.is_valid():
            perfil = form.save()
            auth_login(request, perfil.user)
            messages.success(request, "Cadastro realizado com sucesso! Bem-vindo(a) à Pro Gym.")
            return redirect("index")
    else:
        form = CadastroForm()

    fieldsets = [
        ("Acesso", ["username", "password1", "password2"]),
        ("Dados pessoais", ["first_name", "last_name", "email", "cpf", "data_nasc", "telefone", "endereco"]),
    ]
    return render(request, "registration/cadastro.html", {"form": form, "fieldsets": fieldsets})


@login_required
def perfil(request):
    """O próprio usuário edita seus dados e foto."""
    usuario = request.user
    aluno = usuario.perfil_aluno
    treinador = usuario.perfil_treinador
    if aluno:
        classe_perfil, instancia = MeuPerfilAlunoForm, aluno
    elif treinador:
        classe_perfil, instancia = MeuPerfilTreinadorForm, treinador
    else:
        classe_perfil, instancia = None, None

    if request.method == "POST":
        form_usuario = MeuUsuarioForm(request.POST, instance=usuario)
        form_perfil = classe_perfil(request.POST, request.FILES, instance=instancia) if classe_perfil else None
        usuario_ok = form_usuario.is_valid()
        perfil_ok = form_perfil.is_valid() if form_perfil else True
        if usuario_ok and perfil_ok:
            form_usuario.save()
            if form_perfil:
                form_perfil.save()
            messages.success(request, "Perfil atualizado com sucesso!")
            return redirect("perfil")
        messages.error(request, "Corrija os erros abaixo.")
    else:
        form_usuario = MeuUsuarioForm(instance=usuario)
        form_perfil = classe_perfil(instance=instancia) if classe_perfil else None

    return render(
        request,
        "progym/perfil.html",
        {"form_usuario": form_usuario, "form_perfil": form_perfil, "perfil_obj": instancia},
    )



SECOES_PESSOAIS = [
    (
        "Dados pessoais",
        [
            ("Nome", "user.nome_exibicao"),
            ("Usuário", "user.username"),
            ("E-mail", "user.email"),
            ("CPF", "cpf_formatado"),
            ("Nascimento", "data_nasc"),
            ("Idade", "idade"),
            ("Telefone", "telefone"),
            ("Endereço", "endereco"),
            ("Sobre", "bio"),
        ],
    ),
]

FIELDSETS_PESSOAIS = [
    ("Acesso", ["username", "password1", "password2"]),
    ("Dados pessoais", ["first_name", "last_name", "email", "cpf", "data_nasc", "telefone", "endereco"]),
    ("Academia", ["treinador"]),
    ("Perfil", ["foto", "bio"]),
]


class AlunoBase:
    prefixo = "aluno"
    singular = "aluno"
    plural = "alunos"
    model = Aluno
    perm_gerenciar = "gerenciar_alunos"
    perm_excluir = "excluir_alunos"


class AlunoLista(AlunoBase, ListaBase):
    permissao = "ver_alunos"
    select_related = ("user", "treinador__user")
    campos_busca = ["user__first_name", "user__last_name", "user__username", "cpf", "telefone"]
    texto_busca = "Buscar por nome, usuário, CPF (somente números) ou telefone"
    colunas = [
        ("Nome", "user.nome_exibicao"),
        ("CPF", "cpf_formatado"),
        ("Telefone", "telefone"),
        ("Treinador", "treinador"),
    ]


class AlunoDetalhe(AlunoBase, DetalheBase):
    permissao = "ver_alunos"
    template_name = "progym/crud/aluno_detalhe.html"
    select_related = ("user", "treinador__user")
    secoes = SECOES_PESSOAIS + [("Academia", [("Treinador responsável", "treinador")])]

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        aluno = self.object
        contexto.update(
            treinos=aluno.treino_set.select_related("treinador__user")[:5],
            avaliacoes=aluno.avaliacaofisica_set.all()[:5],
            matriculas=aluno.matricula_set.select_related("academia")[:5],
        )
        return contexto


class AlunoCriar(AlunoBase, CriarBase):
    permissao = "gerenciar_alunos"
    form_class = AlunoForm
    fieldsets = FIELDSETS_PESSOAIS
    success_message = "Aluno cadastrado com sucesso!"

    def get_initial(self):
        inicial = super().get_initial()
        # Treinador que cadastra o aluno já vem como responsável.
        if self.request.user.perfil_treinador:
            inicial["treinador"] = self.request.user.perfil_treinador.pk
        return inicial


class AlunoEditar(AlunoBase, EditarBase):
    permissao = "gerenciar_alunos"
    form_class = AlunoForm
    fieldsets = FIELDSETS_PESSOAIS
    success_message = "Aluno atualizado com sucesso!"


class AlunoExcluir(AlunoBase, ExcluirBase):
    permissao = "excluir_alunos"
    aviso = "Também serão removidos o usuário de acesso, as matrículas, os treinos, as dietas e as avaliações deste aluno."

    def form_valid(self, form):
        nome = str(self.object)
        self.object.user.delete()  # remove o usuário e, em cascata, o perfil e os dados do aluno
        messages.success(self.request, f'Aluno "{nome}" excluído com sucesso.')
        return HttpResponseRedirect(self.get_success_url())




class TreinadorBase:
    prefixo = "treinador"
    singular = "treinador"
    plural = "treinadores"
    model = Treinador
    perm_gerenciar = "gerenciar_treinadores"
    perm_excluir = "gerenciar_treinadores"


class TreinadorLista(TreinadorBase, ListaBase):
    permissao = "ver_treinadores"
    select_related = ("user",)
    campos_busca = ["user__first_name", "user__last_name", "user__username", "cpf", "telefone"]
    texto_busca = "Buscar por nome, usuário, CPF (somente números) ou telefone"
    colunas = [
        ("Nome", "user.nome_exibicao"),
        ("CPF", "cpf_formatado"),
        ("Telefone", "telefone"),
        ("Alunos", "alunos.count"),
    ]


class TreinadorDetalhe(TreinadorBase, DetalheBase):
    permissao = "ver_treinadores"
    select_related = ("user",)
    secoes = SECOES_PESSOAIS


class TreinadorCriar(TreinadorBase, CriarBase):
    permissao = "gerenciar_treinadores"
    form_class = TreinadorForm
    fieldsets = [f for f in FIELDSETS_PESSOAIS if f[0] != "Academia"]
    success_message = "Treinador cadastrado com sucesso!"


class TreinadorEditar(TreinadorBase, EditarBase):
    permissao = "gerenciar_treinadores"
    form_class = TreinadorForm
    fieldsets = [f for f in FIELDSETS_PESSOAIS if f[0] != "Academia"]
    success_message = "Treinador atualizado com sucesso!"


class TreinadorExcluir(TreinadorBase, ExcluirBase):
    permissao = "gerenciar_treinadores"
    aviso = (
        "Também serão removidos o usuário de acesso e os treinos criados por este treinador. "
        "Os alunos ficarão sem treinador responsável."
    )

    def form_valid(self, form):
        nome = str(self.object)
        self.object.user.delete()
        messages.success(self.request, f'Treinador "{nome}" excluído com sucesso.')
        return HttpResponseRedirect(self.get_success_url())
