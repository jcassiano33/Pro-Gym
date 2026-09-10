from django.db import models
from django.contrib.auth.models import AbstractUser


#BÁSICO
class User(AbstractUser):
    pass

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

#TREINO, afins...
class Exercicio(models.Model):
    nome = models.CharField(max_length=100)
    grupo_muscular = models.CharField(max_length=100)
    descricao = models.TextField()
    video = models.URLField(blank=True)

    def __str__(self):
        return self.nome

class Treino(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    treinador = models.ForeignKey(Treinador, on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    descricao = models.TextField()

    def __str__(self):
        return self.nome

class ExercicioTreino(models.Model):
    treino = models.ForeignKey(Treino, on_delete=models.CASCADE)
    exercicio = models.ForeignKey(Exercicio, on_delete=models.CASCADE)
    series = models.IntegerField()
    repeticoes = models.IntegerField()
    carga = models.FloatField()

    def __str__(self):
        return self.exercicio.nome

class RegistroTreino(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    exercicio = models.ForeignKey(Exercicio, on_delete=models.CASCADE)
    carga = models.FloatField()
    repeticoes = models.IntegerField()
    data = models.DateField()

    def __str__(self):
        return self.aluno.nome

class AvaliacaoFisica(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)

    # Dados básicos
    peso = models.FloatField()
    altura = models.FloatField()
    imc = models.FloatField()
    idade_metabolica = models.IntegerField()

    # Composição corporal
    percentual_gordura = models.FloatField()
    massa_gorda = models.FloatField()
    massa_magra = models.FloatField()
    percentual_muscular = models.FloatField()
    agua_corporal = models.FloatField()

    # Medidas em centímetros
    pescoco = models.FloatField()
    ombro = models.FloatField()
    peito = models.FloatField()
    cintura = models.FloatField()
    abdomen = models.FloatField()
    quadril = models.FloatField()

    braco_direito = models.FloatField()
    braco_esquerdo = models.FloatField()

    antebraco_direito = models.FloatField()
    antebraco_esquerdo = models.FloatField()

    coxa_direita = models.FloatField()
    coxa_esquerda = models.FloatField()

    panturrilha_direita = models.FloatField()
    panturrilha_esquerda = models.FloatField()

    data = models.DateField()

    def __str__(self):
        return self.aluno.nome

class Dieta(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    descricao = models.TextField()
    data = models.DateField()

    def __str__(self):
        return self.aluno.nome

class AvaliacaoTreinador(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    treinador = models.ForeignKey(Treinador, on_delete=models.CASCADE)
    nota = models.IntegerField()
    comentario = models.TextField()
    data = models.DateField()

    def __str__(self):
        return self.treinador.nome

class SolicitacaoTreinador(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    treinador = models.ForeignKey(Treinador, on_delete=models.CASCADE)
    motivo = models.TextField()
    data = models.DateField()
    aprovada = models.BooleanField(default=False)

    def __str__(self):
        return self.aluno.nome