from django.db import models

#BÁSICO
class Aluno(models.Model):
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

class Academia(models.Model):
    nome = models.CharField(max_length=100)
    endereco = models.CharField(max_length=200)
    telefone = models.CharField(max_length=20)

    def __str__(self):
        return self.nome

class Matricula(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    academia = models.ForeignKey(Academia, on_delete=models.CASCADE)

    data_inicio = models.DateField()
    data_fim = models.DateField()

    plano = models.CharField(max_length=50)
    valor = models.DecimalField(max_digits=8, decimal_places=2)

    ativa = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.aluno.nome} - {self.academia.nome}"

class Treinador(models.Model):
    nome = models.CharField(max_length=100)
    cpf = models.CharField(max_length=20)
    telefone = models.CharField(max_length=20)
    email = models.CharField(max_length=100)

    def __str__(self):
        return self.nome
