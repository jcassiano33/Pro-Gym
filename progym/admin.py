from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

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
    User,
)


@admin.register(User)
class ProGymUserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "email", "tipo", "is_active")
    list_filter = UserAdmin.list_filter + ("tipo",)
    fieldsets = UserAdmin.fieldsets + (("Pro Gym", {"fields": ("tipo",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Pro Gym", {"fields": ("tipo",)}),)


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "cpf", "telefone", "treinador")
    search_fields = ("user__first_name", "user__last_name", "user__username", "cpf")


@admin.register(Treinador)
class TreinadorAdmin(admin.ModelAdmin):
    list_display = ("__str__", "cpf", "telefone")
    search_fields = ("user__first_name", "user__last_name", "user__username", "cpf")


@admin.register(Academia)
class AcademiaAdmin(admin.ModelAdmin):
    list_display = ("nome", "endereco", "telefone")
    search_fields = ("nome",)


@admin.register(Matricula)
class MatriculaAdmin(admin.ModelAdmin):
    list_display = ("aluno", "academia", "plano", "data_inicio", "data_fim", "valor", "ativa")
    list_filter = ("plano", "ativa", "academia")


@admin.register(Exercicio)
class ExercicioAdmin(admin.ModelAdmin):
    list_display = ("nome", "grupo_muscular")
    list_filter = ("grupo_muscular",)
    search_fields = ("nome",)


class RegistroTreinoInline(admin.TabularInline):
    model = RegistroTreino
    extra = 1


@admin.register(Treino)
class TreinoAdmin(admin.ModelAdmin):
    list_display = ("nome", "aluno", "treinador")
    inlines = [RegistroTreinoInline]


@admin.register(AvaliacaoFisica)
class AvaliacaoFisicaAdmin(admin.ModelAdmin):
    list_display = ("aluno", "data", "peso", "altura", "imc")
    list_filter = ("data",)
    readonly_fields = ("imc",)


class RefeicaoInline(admin.TabularInline):
    model = Refeicao
    extra = 1


@admin.register(Dieta)
class DietaAdmin(admin.ModelAdmin):
    list_display = ("nome", "aluno", "treinador", "objetivo", "calorias_diarias")
    list_filter = ("objetivo",)
    inlines = [RefeicaoInline]


@admin.register(AvaliacaoTreinador)
class AvaliacaoTreinadorAdmin(admin.ModelAdmin):
    list_display = ("aluno", "treinador", "nota", "atualizada_em")
    list_filter = ("nota",)


@admin.register(SolicitacaoTroca)
class SolicitacaoTrocaAdmin(admin.ModelAdmin):
    list_display = ("aluno", "treinador_atual", "treinador_desejado", "status", "criada_em")
    list_filter = ("status",)
