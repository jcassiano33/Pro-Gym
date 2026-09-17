from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("exercicios/<int:id_exercicio>/", views.exercicios, name="exercicios"),
    path("exercicios/novo/", views.novo_exercicio, name="novo_exercicio"),
    path("exercicios/<int:id_exercicio>/editar", views.editar_exercicio, name="editar_exercicio"),
    path("exercicios/<int:id_exercicio>/remover", views.remover_exercicio, name="remover_exercicio"),
]