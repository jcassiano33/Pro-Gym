from django.contrib import admin
from . models import Aluno, Academia, Treinador, Treino, Matricula, Exercicio, RegistroTreino, AvaliacaoFisica

admin.site.register(Aluno)
admin.site.register(Academia)
admin.site.register(Treinador)
admin.site.register(Treino)
admin.site.register(Matricula)
admin.site.register(Exercicio)
admin.site.register(RegistroTreino)
admin.site.register(AvaliacaoFisica)
