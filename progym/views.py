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

# ===========================================================================
# Autenticação e perfil
# ===========================================================================

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

# ===========================================================================
# Alunos
# ===========================================================================

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


# ===========================================================================
# Treinadores
# ===========================================================================

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
# ===========================================================================
# Academias
# ===========================================================================
class AcademiaBase:
    prefixo = "academia"
    singular = "academia"
    plural = "academias"
    model = Academia
    perm_gerenciar = "gerenciar_academias"
    perm_excluir = "gerenciar_academias"


class AcademiaLista(AcademiaBase, ListaBase):
    permissao = "ver_academias"
    campos_busca = ["nome", "endereco"]
    texto_busca = "Buscar por nome ou endereço"
    colunas = [("Nome", "nome"), ("Endereço", "endereco"), ("Telefone", "telefone")]


class AcademiaDetalhe(AcademiaBase, DetalheBase):
    permissao = "ver_academias"
    secoes = [("Academia", [("Nome", "nome"), ("Endereço", "endereco"), ("Telefone", "telefone")])]


class AcademiaCriar(AcademiaBase, CriarBase):
    permissao = "gerenciar_academias"
    form_class = AcademiaForm
    success_message = "Academia cadastrada com sucesso!"


class AcademiaEditar(AcademiaBase, EditarBase):
    permissao = "gerenciar_academias"
    form_class = AcademiaForm
    success_message = "Academia atualizada com sucesso!"


class AcademiaExcluir(AcademiaBase, ExcluirBase):
    permissao = "gerenciar_academias"
    aviso = "As matrículas vinculadas a esta academia também serão removidas."


# ===========================================================================
# Matrículas
# ===========================================================================
class MatriculaBase:
    prefixo = "matricula"
    singular = "matrícula"
    plural = "matrículas"
    model = Matricula
    perm_gerenciar = "gerenciar_matriculas"
    perm_excluir = "gerenciar_matriculas"

    def escopo(self, queryset):
        return somente_do_aluno(queryset, self.request.user)


class MatriculaLista(MatriculaBase, ListaBase):
    permissao = "ver_matriculas"
    select_related = ("aluno__user", "academia")
    campos_busca = ["aluno__user__first_name", "aluno__user__last_name", "academia__nome", "plano"]
    texto_busca = "Buscar por aluno, academia ou plano"
    colunas = [
        ("Aluno", "aluno"),
        ("Academia", "academia"),
        ("Plano", "get_plano_display"),
        ("Início", "data_inicio"),
        ("Término", "data_fim"),
        ("Valor (R$)", "valor"),
        ("Situação", "situacao"),
    ]


class MatriculaDetalhe(MatriculaBase, DetalheBase):
    permissao = "ver_matriculas"
    select_related = ("aluno__user", "academia")
    secoes = [
        (
            "Matrícula",
            [
                ("Aluno", "aluno"),
                ("Academia", "academia"),
                ("Plano", "get_plano_display"),
                ("Início", "data_inicio"),
                ("Término", "data_fim"),
                ("Valor (R$)", "valor"),
                ("Situação", "situacao"),
            ],
        )
    ]


class MatriculaCriar(MatriculaBase, CriarBase):
    permissao = "gerenciar_matriculas"
    form_class = MatriculaForm
    success_message = "Matrícula registrada com sucesso!"


class MatriculaEditar(MatriculaBase, EditarBase):
    permissao = "gerenciar_matriculas"
    form_class = MatriculaForm
    success_message = "Matrícula atualizada com sucesso!"


class MatriculaExcluir(MatriculaBase, ExcluirBase):
    permissao = "gerenciar_matriculas"


# ===========================================================================
# Exercícios
# ===========================================================================
class ExercicioBase:
    prefixo = "exercicio"
    singular = "exercício"
    plural = "exercícios"
    model = Exercicio
    perm_gerenciar = "gerenciar_exercicios"
    perm_excluir = "gerenciar_exercicios"


class ExercicioLista(ExercicioBase, ListaBase):
    permissao = "ver_exercicios"
    campos_busca = ["nome", "grupo_muscular", "descricao"]
    texto_busca = "Buscar por nome ou descrição"
    colunas = [("Nome", "nome"), ("Grupo muscular", "get_grupo_muscular_display"), ("Vídeo", "video")]

    def get_queryset(self):
        queryset = super().get_queryset()
        grupo = self.request.GET.get("grupo", "").strip()
        if grupo:
            queryset = queryset.filter(grupo_muscular=grupo)
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        grupo = self.request.GET.get("grupo", "").strip()
        contexto["filtro_grupos"] = Exercicio.GRUPOS
        contexto["grupo_selecionado"] = grupo
        if grupo:
            contexto["qs_extra"] += "&" + urlencode({"grupo": grupo})
        return contexto


class ExercicioDetalhe(ExercicioBase, DetalheBase):
    permissao = "ver_exercicios"
    secoes = [
        (
            "Exercício",
            [
                ("Nome", "nome"),
                ("Grupo muscular", "get_grupo_muscular_display"),
                ("Descrição", "descricao"),
                ("Vídeo", "video"),
            ],
        )
    ]


class ExercicioCriar(ExercicioBase, CriarBase):
    permissao = "gerenciar_exercicios"
    form_class = ExercicioForm
    success_message = "Exercício cadastrado com sucesso!"


class ExercicioEditar(ExercicioBase, EditarBase):
    permissao = "gerenciar_exercicios"
    form_class = ExercicioForm
    success_message = "Exercício atualizado com sucesso!"


class ExercicioExcluir(ExercicioBase, ExcluirBase):
    permissao = "gerenciar_exercicios"
    aviso = "Ele também será removido de todos os treinos em que aparece."


# ===========================================================================
# Treinos
# ===========================================================================
class TreinoBase:
    prefixo = "treino"
    singular = "treino"
    plural = "treinos"
    model = Treino
    perm_gerenciar = "gerenciar_treinos"
    perm_excluir = "gerenciar_treinos"


class TreinoLista(TreinoBase, ListaBase):
    permissao = "ver_treinos"
    select_related = ("aluno__user", "treinador__user")
    campos_busca = ["nome", "aluno__user__first_name", "aluno__user__last_name"]
    texto_busca = "Buscar por nome do treino ou do aluno"
    colunas = [
        ("Treino", "nome"),
        ("Aluno", "aluno"),
        ("Treinador", "treinador"),
        ("Exercícios", "registros.count"),
    ]

    def escopo(self, queryset):
        return treinos_visiveis(self.request.user)


class TreinoDetalhe(TreinoBase, DetalheBase):
    permissao = "ver_treinos"
    template_name = "progym/crud/treino_detalhe.html"
    select_related = ("aluno__user", "treinador__user")
    secoes = [
        (
            "Treino",
            [("Nome", "nome"), ("Aluno", "aluno"), ("Treinador", "treinador"), ("Descrição", "descricao")],
        )
    ]

    def escopo(self, queryset):
        return treinos_visiveis(self.request.user)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        usuario = self.request.user
        contexto["registros"] = self.object.registros.select_related("exercicio")
        contexto["pode_editar"] = (
            usuario_pode(usuario, "gerenciar_treinos")
            and treinos_gerenciaveis(usuario).filter(pk=self.object.pk).exists()
        )
        return contexto


class TreinoFormMixin:
    form_class = TreinoForm
    fieldsets = [("Treino", ["aluno", "treinador", "nome", "descricao"])]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class TreinoCriar(TreinoFormMixin, TreinoBase, CriarBase):
    permissao = "gerenciar_treinos"
    success_message = "Treino criado com sucesso!"

    def form_valid(self, form):
        if not self.request.user.is_administrador:
            treinador = self.request.user.perfil_treinador
            if treinador is None:
                form.add_error(None, "Seu usuário não possui perfil de treinador.")
                return self.form_invalid(form)
            form.instance.treinador = treinador
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("treino_detail", args=[self.object.pk])


class TreinoEditar(TreinoFormMixin, TreinoBase, EditarBase):
    permissao = "gerenciar_treinos"
    success_message = "Treino atualizado com sucesso!"

    def escopo(self, queryset):
        return treinos_gerenciaveis(self.request.user)

    def get_success_url(self):
        return reverse("treino_detail", args=[self.object.pk])


class TreinoExcluir(TreinoBase, ExcluirBase):
    permissao = "gerenciar_treinos"
    aviso = "Os exercícios deste treino também serão removidos."

    def escopo(self, queryset):
        return treinos_gerenciaveis(self.request.user)


# --- exercícios dentro de um treino ---------------------------------------
class RegistroBase:
    prefixo = "registro"
    singular = "exercício do treino"
    plural = "exercícios do treino"
    model = RegistroTreino
    permissao = "gerenciar_treinos"
    perm_gerenciar = "gerenciar_treinos"
    perm_excluir = "gerenciar_treinos"


class RegistroCriar(RegistroBase, CriarBase):
    form_class = RegistroTreinoForm
    success_message = "Exercício adicionado ao treino!"

    def get_treino(self):
        if not hasattr(self, "_treino"):
            self._treino = get_object_or_404(treinos_gerenciaveis(self.request.user), pk=self.kwargs["treino_pk"])
        return self._treino

    def get_voltar_url(self):
        return reverse("treino_detail", args=[self.get_treino().pk])

    def get_success_url(self):
        return self.get_voltar_url()

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["subtitulo"] = f"Treino: {self.get_treino().nome}"
        return contexto

    def form_valid(self, form):
        form.instance.treino = self.get_treino()
        return super().form_valid(form)


class RegistroEditar(RegistroBase, EditarBase):
    form_class = RegistroTreinoForm
    success_message = "Exercício do treino atualizado!"

    def escopo(self, queryset):
        return queryset.filter(treino__in=treinos_gerenciaveis(self.request.user)).select_related("treino", "exercicio")

    def get_voltar_url(self):
        return reverse("treino_detail", args=[self.object.treino_id])

    def get_success_url(self):
        return self.get_voltar_url()

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["subtitulo"] = f"Treino: {self.object.treino.nome}"
        return contexto


class RegistroExcluir(RegistroBase, ExcluirBase):
    aviso = ""

    def escopo(self, queryset):
        return queryset.filter(treino__in=treinos_gerenciaveis(self.request.user)).select_related("treino", "exercicio")

    def get_voltar_url(self):
        return reverse("treino_detail", args=[self.object.treino_id])

    def get_success_url(self):
        return reverse("treino_detail", args=[self.object.treino_id])


# ===========================================================================
# Avaliações físicas
# ===========================================================================
CAMPOS_MEDIDAS = [
    "pescoco", "ombro", "peito", "cintura", "abdomen", "quadril",
    "braco_direito", "braco_esquerdo", "antebraco_direito", "antebraco_esquerdo",
    "coxa_direita", "coxa_esquerda", "panturrilha_direita", "panturrilha_esquerda",
]  # fmt: skip
CAMPOS_COMPOSICAO = ["percentual_gordura", "massa_gorda", "massa_magra", "percentual_muscular", "agua_corporal"]


class AvaliacaoBase:
    prefixo = "avaliacao"
    singular = "avaliação física"
    plural = "avaliações físicas"
    model = AvaliacaoFisica
    perm_gerenciar = "gerenciar_avaliacoes"
    perm_excluir = "gerenciar_avaliacoes"

    def escopo(self, queryset):
        return somente_do_aluno(queryset, self.request.user)


def _rotulo(nome):
    return AvaliacaoFisica._meta.get_field(nome).verbose_name.capitalize()


class AvaliacaoLista(AvaliacaoBase, ListaBase):
    permissao = "ver_avaliacoes"
    select_related = ("aluno__user",)
    campos_busca = ["aluno__user__first_name", "aluno__user__last_name"]
    texto_busca = "Buscar por nome do aluno"
    colunas = [
        ("Aluno", "aluno"),
        ("Data", "data"),
        ("Peso (kg)", "peso"),
        ("Altura (m)", "altura"),
        ("IMC", "imc"),
        ("Classificação", "classificacao_imc"),
    ]


class AvaliacaoDetalhe(AvaliacaoBase, DetalheBase):
    permissao = "ver_avaliacoes"
    select_related = ("aluno__user",)
    secoes = [
        (
            "Dados básicos",
            [
                ("Aluno", "aluno"),
                ("Data", "data"),
                ("Peso (kg)", "peso"),
                ("Altura (m)", "altura"),
                ("IMC", "imc"),
                ("Classificação do IMC", "classificacao_imc"),
                ("Idade metabólica", "idade_metabolica"),
            ],
        ),
        ("Composição corporal", [(_rotulo(c), c) for c in CAMPOS_COMPOSICAO]),
        ("Medidas", [(_rotulo(c), c) for c in CAMPOS_MEDIDAS]),
    ]


FIELDSETS_AVALIACAO = [
    ("Dados básicos", ["aluno", "data", "peso", "altura", "idade_metabolica"]),
    ("Composição corporal", CAMPOS_COMPOSICAO),
    ("Medidas (cm)", CAMPOS_MEDIDAS),
]


class AvaliacaoCriar(AvaliacaoBase, CriarBase):
    permissao = "gerenciar_avaliacoes"
    form_class = AvaliacaoFisicaForm
    fieldsets = FIELDSETS_AVALIACAO
    success_message = "Avaliação física registrada com sucesso!"


class AvaliacaoEditar(AvaliacaoBase, EditarBase):
    permissao = "gerenciar_avaliacoes"
    form_class = AvaliacaoFisicaForm
    fieldsets = FIELDSETS_AVALIACAO
    success_message = "Avaliação física atualizada com sucesso!"


class AvaliacaoExcluir(AvaliacaoBase, ExcluirBase):
    permissao = "gerenciar_avaliacoes"


# ===========================================================================
# Dietas
# ===========================================================================
def dietas_visiveis(user):
    if user.is_administrador:
        return Dieta.objects.all()
    if user.is_treinador and user.perfil_treinador:
        return Dieta.objects.filter(treinador=user.perfil_treinador)
    if user.is_aluno and user.perfil_aluno:
        return Dieta.objects.filter(aluno=user.perfil_aluno)
    return Dieta.objects.none()


def dietas_gerenciaveis(user):
    """Administrador altera qualquer dieta; treinador, apenas as suas."""
    if user.is_administrador:
        return Dieta.objects.all()
    if user.is_treinador and user.perfil_treinador:
        return Dieta.objects.filter(treinador=user.perfil_treinador)
    return Dieta.objects.none()


class DietaBase:
    prefixo = "dieta"
    singular = "dieta"
    plural = "dietas"
    model = Dieta
    perm_gerenciar = "gerenciar_dietas"
    perm_excluir = "gerenciar_dietas"


class DietaLista(DietaBase, ListaBase):
    permissao = "ver_dietas"
    select_related = ("aluno__user", "treinador__user")
    campos_busca = ["nome", "aluno__user__first_name", "aluno__user__last_name"]
    texto_busca = "Buscar por nome da dieta ou do aluno"
    colunas = [
        ("Dieta", "nome"),
        ("Aluno", "aluno"),
        ("Objetivo", "get_objetivo_display"),
        ("Meta (kcal/dia)", "calorias_diarias"),
        ("Refeições", "refeicoes.count"),
    ]

    def escopo(self, queryset):
        return dietas_visiveis(self.request.user)


class DietaDetalhe(DietaBase, DetalheBase):
    permissao = "ver_dietas"
    template_name = "progym/crud/dieta_detalhe.html"
    select_related = ("aluno__user", "treinador__user")
    secoes = [
        (
            "Plano alimentar",
            [
                ("Nome", "nome"),
                ("Aluno", "aluno"),
                ("Treinador", "treinador"),
                ("Objetivo", "get_objetivo_display"),
                ("Meta diária (kcal)", "calorias_diarias"),
                ("Descrição", "descricao"),
            ],
        )
    ]

    def escopo(self, queryset):
        return dietas_visiveis(self.request.user)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        usuario = self.request.user
        refeicoes = sorted(self.object.refeicoes.all(), key=lambda r: (r.ordem, r.pk))
        contexto["refeicoes"] = refeicoes
        contexto["total_calorias"] = sum(r.calorias or 0 for r in refeicoes)
        contexto["pode_editar"] = (
            usuario_pode(usuario, "gerenciar_dietas")
            and dietas_gerenciaveis(usuario).filter(pk=self.object.pk).exists()
        )
        return contexto


class DietaFormMixin:
    form_class = DietaForm
    fieldsets = [("Dieta", ["aluno", "treinador", "nome", "objetivo", "calorias_diarias", "descricao"])]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class DietaCriar(DietaFormMixin, DietaBase, CriarBase):
    permissao = "gerenciar_dietas"
    success_message = "Dieta criada com sucesso!"

    def form_valid(self, form):
        if not self.request.user.is_administrador:
            treinador = self.request.user.perfil_treinador
            if treinador is None:
                form.add_error(None, "Seu usuário não possui perfil de treinador.")
                return self.form_invalid(form)
            form.instance.treinador = treinador
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("dieta_detail", args=[self.object.pk])


class DietaEditar(DietaFormMixin, DietaBase, EditarBase):
    permissao = "gerenciar_dietas"
    success_message = "Dieta atualizada com sucesso!"

    def escopo(self, queryset):
        return dietas_gerenciaveis(self.request.user)

    def get_success_url(self):
        return reverse("dieta_detail", args=[self.object.pk])


class DietaExcluir(DietaBase, ExcluirBase):
    permissao = "gerenciar_dietas"
    aviso = "As refeições desta dieta também serão removidas."

    def escopo(self, queryset):
        return dietas_gerenciaveis(self.request.user)


# --- refeições dentro de uma dieta ----------------------------------------
class RefeicaoBase:
    prefixo = "refeicao"
    singular = "refeição"
    plural = "refeições"
    model = Refeicao
    permissao = "gerenciar_dietas"
    perm_gerenciar = "gerenciar_dietas"
    perm_excluir = "gerenciar_dietas"


class RefeicaoCriar(RefeicaoBase, CriarBase):
    form_class = RefeicaoForm
    success_message = "Refeição adicionada à dieta!"

    def get_dieta(self):
        if not hasattr(self, "_dieta"):
            self._dieta = get_object_or_404(dietas_gerenciaveis(self.request.user), pk=self.kwargs["dieta_pk"])
        return self._dieta

    def get_voltar_url(self):
        return reverse("dieta_detail", args=[self.get_dieta().pk])

    def get_success_url(self):
        return self.get_voltar_url()

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["subtitulo"] = f"Dieta: {self.get_dieta().nome}"
        return contexto

    def form_valid(self, form):
        form.instance.dieta = self.get_dieta()
        return super().form_valid(form)


class RefeicaoEditar(RefeicaoBase, EditarBase):
    form_class = RefeicaoForm
    success_message = "Refeição atualizada!"

    def escopo(self, queryset):
        return queryset.filter(dieta__in=dietas_gerenciaveis(self.request.user)).select_related("dieta")

    def get_voltar_url(self):
        return reverse("dieta_detail", args=[self.object.dieta_id])

    def get_success_url(self):
        return self.get_voltar_url()

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["subtitulo"] = f"Dieta: {self.object.dieta.nome}"
        return contexto


class RefeicaoExcluir(RefeicaoBase, ExcluirBase):
    def escopo(self, queryset):
        return queryset.filter(dieta__in=dietas_gerenciaveis(self.request.user)).select_related("dieta")

    def get_voltar_url(self):
        return reverse("dieta_detail", args=[self.object.dieta_id])

    def get_success_url(self):
        return reverse("dieta_detail", args=[self.object.dieta_id])


# ===========================================================================
# Meu treinador, avaliação do treinador e troca de treinador
# ===========================================================================
@permissao_requerida("avaliar_treinador")
def meu_treinador(request):
    aluno = request.user.perfil_aluno
    contexto = {"aluno": aluno, "treinador": None, "resumo": None, "minha_avaliacao": None, "troca_pendente": None}
    if aluno is not None:
        treinador = aluno.treinador
        contexto["treinador"] = treinador
        contexto["troca_pendente"] = SolicitacaoTroca.objects.filter(
            aluno=aluno, status=SolicitacaoTroca.PENDENTE
        ).first()
        if treinador is not None:
            contexto["resumo"] = treinador.avaliacoes_recebidas.aggregate(media=Avg("nota"), total=Count("id"))
            contexto["minha_avaliacao"] = AvaliacaoTreinador.objects.filter(aluno=aluno, treinador=treinador).first()
    return render(request, "progym/meu_treinador.html", contexto)


@permissao_requerida("avaliar_treinador")
def avaliar_treinador(request):
    """O aluno cria (ou altera) a sua avaliação do treinador atual."""
    aluno = request.user.perfil_aluno
    if aluno is None or aluno.treinador is None:
        messages.warning(request, "Você precisa ter um treinador responsável para poder avaliá-lo.")
        return redirect("meu_treinador")

    treinador = aluno.treinador
    existente = AvaliacaoTreinador.objects.filter(aluno=aluno, treinador=treinador).first()
    if request.method == "POST":
        form = AvaliacaoTreinadorForm(request.POST, instance=existente)
        if form.is_valid():
            avaliacao = form.save(commit=False)
            avaliacao.aluno = aluno
            avaliacao.treinador = treinador
            avaliacao.save()
            messages.success(request, "Obrigado! Sua avaliação foi registrada.")
            return redirect("meu_treinador")
    else:
        form = AvaliacaoTreinadorForm(instance=existente)

    return render(
        request,
        "progym/crud/form.html",
        {
            "form": form,
            "fieldsets": [(None, ["nota", "comentario"])],
            "titulo_pagina": "Avaliar treinador" if existente is None else "Alterar minha avaliação",
            "subtitulo": f"Treinador: {treinador}",
            "voltar_url": reverse("meu_treinador"),
        },
    )


class AvaliacaoTreinadorBase:
    prefixo = "avaliacao_treinador"
    singular = "avaliação de treinador"
    plural = "avaliações de treinadores"
    model = AvaliacaoTreinador
    perm_excluir = "gerenciar_avaliacoes_treinador"
    tem_detalhe = False

    def escopo(self, queryset):
        usuario = self.request.user
        if usuario.is_administrador:
            return queryset
        if usuario.is_treinador and usuario.perfil_treinador:
            return queryset.filter(treinador=usuario.perfil_treinador)
        if usuario.is_aluno and usuario.perfil_aluno:
            return queryset.filter(aluno=usuario.perfil_aluno)
        return queryset.none()


class AvaliacaoTreinadorLista(AvaliacaoTreinadorBase, ListaBase):
    permissao = "ver_avaliacoes_treinador"
    select_related = ("aluno__user", "treinador__user")
    campos_busca = [
        "aluno__user__first_name",
        "aluno__user__last_name",
        "treinador__user__first_name",
        "treinador__user__last_name",
        "comentario",
    ]
    texto_busca = "Buscar por aluno, treinador ou comentário"
    colunas = [
        ("Aluno", "aluno"),
        ("Treinador", "treinador"),
        ("Nota", "estrelas"),
        ("Comentário", "comentario"),
        ("Atualizada em", "atualizada_em"),
    ]


class AvaliacaoTreinadorExcluir(AvaliacaoTreinadorBase, ExcluirBase):
    permissao = "gerenciar_avaliacoes_treinador"


# --- solicitação de troca ---------------------------------------------------
def trocas_visiveis(user):
    if user.is_administrador:
        return SolicitacaoTroca.objects.all()
    if user.is_treinador and user.perfil_treinador:
        return SolicitacaoTroca.objects.filter(treinador_atual=user.perfil_treinador)
    if user.is_aluno and user.perfil_aluno:
        return SolicitacaoTroca.objects.filter(aluno=user.perfil_aluno)
    return SolicitacaoTroca.objects.none()


class TrocaBase:
    prefixo = "troca"
    singular = "solicitação de troca"
    plural = "solicitações de troca"
    model = SolicitacaoTroca
    perm_gerenciar = "solicitar_troca"  # só o aluno cria; ninguém edita
    perm_excluir = None
    permite_editar = False
    rotulo_novo = "Solicitar troca de treinador"
    titulo_novo = "Solicitar troca de treinador"

    def escopo(self, queryset):
        return trocas_visiveis(self.request.user)


class TrocaLista(TrocaBase, ListaBase):
    permissao = "ver_trocas"
    select_related = ("aluno__user", "treinador_atual__user", "treinador_desejado__user")
    campos_busca = ["aluno__user__first_name", "aluno__user__last_name", "motivo"]
    texto_busca = "Buscar por aluno ou motivo"
    colunas = [
        ("Aluno", "aluno"),
        ("Treinador atual", "treinador_atual"),
        ("Treinador desejado", "treinador_desejado"),
        ("Situação", "get_status_display"),
        ("Solicitada em", "criada_em"),
    ]


class TrocaDetalhe(TrocaBase, DetalheBase):
    permissao = "ver_trocas"
    template_name = "progym/crud/troca_detalhe.html"
    select_related = ("aluno__user", "treinador_atual__user", "treinador_desejado__user", "respondida_por")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        usuario = self.request.user
        troca = self.object
        pendente = troca.status == SolicitacaoTroca.PENDENTE
        pode_responder = pendente and usuario_pode(usuario, "responder_trocas")
        contexto["pode_responder"] = pode_responder
        contexto["pode_cancelar"] = (
            pendente and usuario.is_aluno and usuario.perfil_aluno is not None and troca.aluno_id == usuario.perfil_aluno.pk
        )
        if pode_responder:
            contexto["form_resposta"] = RespostaTrocaForm(
                initial={"novo_treinador": troca.treinador_desejado_id, "decisao": "aprovada"}
            )
        return contexto


class TrocaCriar(TrocaBase, CriarBase):
    permissao = "solicitar_troca"
    form_class = SolicitacaoTrocaForm
    success_message = "Solicitação enviada! Você será avisado quando for respondida."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        aluno = self.request.user.perfil_aluno
        if aluno is None:
            form.add_error(None, "Seu usuário não possui perfil de aluno.")
            return self.form_invalid(form)
        if SolicitacaoTroca.objects.filter(aluno=aluno, status=SolicitacaoTroca.PENDENTE).exists():
            form.add_error(None, "Você já possui uma solicitação pendente. Aguarde a resposta ou cancele-a.")
            return self.form_invalid(form)
        form.instance.aluno = aluno
        form.instance.treinador_atual = aluno.treinador
        return super().form_valid(form)


@permissao_requerida("solicitar_troca")
@require_POST
def troca_cancelar(request, pk):
    """O aluno cancela uma solicitação que ainda está pendente."""
    troca = get_object_or_404(trocas_visiveis(request.user), pk=pk)
    if troca.status != SolicitacaoTroca.PENDENTE:
        messages.error(request, "Apenas solicitações pendentes podem ser canceladas.")
    else:
        troca.status = SolicitacaoTroca.CANCELADA
        troca.save(update_fields=["status"])
        messages.success(request, "Solicitação cancelada.")
    return redirect("troca_detail", pk=troca.pk)


@permissao_requerida("responder_trocas")
@require_POST
def troca_responder(request, pk):
    """A administração aprova (definindo o novo treinador) ou recusa a solicitação."""
    troca = get_object_or_404(SolicitacaoTroca.objects.select_related("aluno"), pk=pk)
    if troca.status != SolicitacaoTroca.PENDENTE:
        messages.error(request, "Esta solicitação já foi respondida.")
        return redirect("troca_detail", pk=troca.pk)

    form = RespostaTrocaForm(request.POST)
    if not form.is_valid():
        for erros in form.errors.values():
            for erro in erros:
                messages.error(request, erro)
        return redirect("troca_detail", pk=troca.pk)

    dados = form.cleaned_data
    with transaction.atomic():
        troca.status = dados["decisao"]
        troca.resposta = dados["resposta"]
        troca.respondida_em = timezone.now()
        troca.respondida_por = request.user
        troca.save()
        if dados["decisao"] == SolicitacaoTroca.APROVADA:
            aluno = troca.aluno
            aluno.treinador = dados["novo_treinador"]
            aluno.save(update_fields=["treinador"])

    if dados["decisao"] == SolicitacaoTroca.APROVADA:
        messages.success(request, f"Troca aprovada: {troca.aluno} agora é atendido(a) por {dados['novo_treinador']}.")
    else:
        messages.success(request, "Solicitação recusada.")
    return redirect("troca_detail", pk=troca.pk)
