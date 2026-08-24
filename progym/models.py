from django.db import models

class Aluno(models.Models):
    nome = models.CharField(max_length=100)
    cpf = models.CharField(max_length=100)
    data_nasc = models.DateField()

    telefone = models.CharField(max_length=100)
    email = models.CharField(max_length=100)
    endereco = models.CharField(max_length=100)

    senha = models.CharField(max_length=100)

    foto = models.ImageField(upload_to="media")
    bio = models.TextField(max_length=200)

    def __str__(self):
        return self.nome