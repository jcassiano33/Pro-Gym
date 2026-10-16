from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm, NovaSenhaForm, RecuperarSenhaForm, SenhaAlteracaoForm


def crud(prefixo, rota, lista, criar, detalhe, editar, excluir):
    return [
        path(f"{rota}/", lista.as_view(), name=f"{prefixo}_list"),
        path(f"{rota}/novo/", criar.as_view(), name=f"{prefixo}_create"),
        path(f"{rota}/<int:pk>/", detalhe.as_view(), name=f"{prefixo}_detail"),
        path(f"{rota}/<int:pk>/editar/", editar.as_view(), name=f"{prefixo}_update"),
        path(f"{rota}/<int:pk>/excluir/", excluir.as_view(), name=f"{prefixo}_delete"),
    ]


urlpatterns = [
    path("", views.index, name="index"),
    path("perfil/", views.perfil, name="perfil"),
    # ----- autenticação -----
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=LoginForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/cadastro/", views.cadastro, name="cadastro"),
    path(
        "accounts/senha/alterar/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/alterar_senha.html",
            form_class=SenhaAlteracaoForm,
        ),
        name="password_change",
    ),
    path(
        "accounts/senha/alterar/concluido/",
        auth_views.PasswordChangeDoneView.as_view(template_name="registration/alterar_senha_concluido.html"),
        name="password_change_done",
    ),
    path(
        "accounts/password_reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/recuperar_senha.html",
            email_template_name="registration/email_recuperar_senha.txt",
            subject_template_name="registration/email_assunto.txt",
            form_class=RecuperarSenhaForm,
        ),
        name="password_reset",
    ),
    path(
        "accounts/password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="registration/recuperar_senha_enviado.html"),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/recuperar_senha_confirmar.html",
            form_class=NovaSenhaForm,
        ),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="registration/recuperar_senha_concluido.html"),
        name="password_reset_complete",
    ),
]

# ----- CRUDs -----
urlpatterns += crud(
    "aluno", "alunos",
    views.AlunoLista, views.AlunoCriar, views.AlunoDetalhe, views.AlunoEditar, views.AlunoExcluir,
)  # fmt: skip
urlpatterns += crud(
    "treinador", "treinadores",
    views.TreinadorLista, views.TreinadorCriar, views.TreinadorDetalhe, views.TreinadorEditar, views.TreinadorExcluir,
)  # fmt: skip
urlpatterns += crud(
    "academia", "academias",
    views.AcademiaLista, views.AcademiaCriar, views.AcademiaDetalhe, views.AcademiaEditar, views.AcademiaExcluir,
)  # fmt: skip
urlpatterns += crud(
    "matricula", "matriculas",
    views.MatriculaLista, views.MatriculaCriar, views.MatriculaDetalhe, views.MatriculaEditar, views.MatriculaExcluir,
)  # fmt: skip
urlpatterns += crud(
    "exercicio", "exercicios",
    views.ExercicioLista, views.ExercicioCriar, views.ExercicioDetalhe, views.ExercicioEditar, views.ExercicioExcluir,
)  # fmt: skip
urlpatterns += crud(
    "treino", "treinos",
    views.TreinoLista, views.TreinoCriar, views.TreinoDetalhe, views.TreinoEditar, views.TreinoExcluir,
)  # fmt: skip
urlpatterns += crud(
    "avaliacao", "avaliacoes",
    views.AvaliacaoLista, views.AvaliacaoCriar, views.AvaliacaoDetalhe, views.AvaliacaoEditar, views.AvaliacaoExcluir,
)  # fmt: skip

# ----- exercícios dentro de um treino -----
urlpatterns += [
    path("treinos/<int:treino_pk>/exercicios/novo/", views.RegistroCriar.as_view(), name="registro_create"),
    path("treinos/exercicios/<int:pk>/editar/", views.RegistroEditar.as_view(), name="registro_update"),
    path("treinos/exercicios/<int:pk>/excluir/", views.RegistroExcluir.as_view(), name="registro_delete"),
]

# ----- refeições dentro de uma dieta -----
urlpatterns += [
    path("dietas/<int:dieta_pk>/refeicoes/nova/", views.RefeicaoCriar.as_view(), name="refeicao_create"),
    path("dietas/refeicoes/<int:pk>/editar/", views.RefeicaoEditar.as_view(), name="refeicao_update"),
    path("dietas/refeicoes/<int:pk>/excluir/", views.RefeicaoExcluir.as_view(), name="refeicao_delete"),
]

# ----- dietas -----
urlpatterns += crud(
    "dieta", "dietas",
    views.DietaLista, views.DietaCriar, views.DietaDetalhe, views.DietaEditar, views.DietaExcluir,
)  # fmt: skip

# ----- meu treinador: avaliação e troca -----
urlpatterns += [
    path("meu-treinador/", views.meu_treinador, name="meu_treinador"),
    path("meu-treinador/avaliar/", views.avaliar_treinador, name="avaliar_treinador"),
    path("avaliacoes-treinadores/", views.AvaliacaoTreinadorLista.as_view(), name="avaliacao_treinador_list"),
    path(
        "avaliacoes-treinadores/<int:pk>/excluir/",
        views.AvaliacaoTreinadorExcluir.as_view(),
        name="avaliacao_treinador_delete",
    ),
    path("trocas/", views.TrocaLista.as_view(), name="troca_list"),
    path("trocas/nova/", views.TrocaCriar.as_view(), name="troca_create"),
    path("trocas/<int:pk>/", views.TrocaDetalhe.as_view(), name="troca_detail"),
    path("trocas/<int:pk>/cancelar/", views.troca_cancelar, name="troca_cancelar"),
    path("trocas/<int:pk>/responder/", views.troca_responder, name="troca_responder"),
]
