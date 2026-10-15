from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from .validators import (
    validate_cpf,
    validate_data_nascimento,
    validate_telefone,
)


# ---------------------------------------------------------------------------
# Usuário e perfis
# ---------------------------------------------------------------------------
class User(AbstractUser):
    ADMINISTRADOR = "administrador"
    TREINADOR = "treinador"
    ALUNO = "aluno"

    tipo_users = (
        (ADMINISTRADOR, "Administrador"),
        (TREINADOR, "Treinador"),
        (ALUNO, "Aluno"),
    )

    tipo = models.CharField("Perfil de acesso", max_length=20, choices=tipo_users, default=ALUNO)

    def save(self, *args, **kwargs):
        # Quem é superusuário (createsuperuser) sempre tem perfil de administrador.
        if self.is_superuser:
            self.tipo = self.ADMINISTRADOR
        super().save(*args, **kwargs)

    @property
    def nome_exibicao(self):
        return self.get_full_name() or self.username

    @property
    def primeiro_nome(self):
        return self.first_name or self.username

    @property
    def is_administrador(self):
        return self.is_superuser or self.tipo == self.ADMINISTRADOR

    @property
    def is_treinador(self):
        return self.tipo == self.TREINADOR

    @property
    def is_aluno(self):
        return self.tipo == self.ALUNO

    @property
    def perfil_aluno(self):
        """Perfil de aluno ou None (evita exceção quando o usuário não possui)."""
        return getattr(self, "aluno", None)

    @property
    def perfil_treinador(self):
        return getattr(self, "treinador", None)


class PerfilBase(models.Model):
    """Campos comuns a Aluno e Treinador."""

    cpf = models.CharField("CPF", max_length=14, unique=True, validators=[validate_cpf])
    data_nasc = models.DateField("Data de nascimento", validators=[validate_data_nascimento])
    telefone = models.CharField("Telefone", max_length=20, validators=[validate_telefone])
    endereco = models.CharField("Endereço", max_length=200)
    foto = models.ImageField("Foto", upload_to="fotos/", blank=True)
    bio = models.TextField("Sobre", max_length=200, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.user.nome_exibicao

    @property
    def cpf_formatado(self):
        c = self.cpf or ""
        return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c) == 11 else c

    @property
    def idade(self):
        hoje = timezone.localdate()
        return hoje.year - self.data_nasc.year - (
            (hoje.month, hoje.day) < (self.data_nasc.month, self.data_nasc.day)
        )


class Treinador(PerfilBase):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "treinador"
        verbose_name_plural = "treinadores"
        ordering = ["user__first_name", "user__username"]


class Aluno(PerfilBase):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    treinador = models.ForeignKey(
        Treinador,
        verbose_name="Treinador responsável",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alunos",
    )

    class Meta:
        verbose_name = "aluno"
        verbose_name_plural = "alunos"
        ordering = ["user__first_name", "user__username"]


# ---------------------------------------------------------------------------
# Academia e matrícula
# ---------------------------------------------------------------------------
class Academia(models.Model):
    nome = models.CharField(max_length=100)
    endereco = models.CharField("Endereço", max_length=200)
    telefone = models.CharField(max_length=20, validators=[validate_telefone])

    class Meta:
        verbose_name = "academia"
        verbose_name_plural = "academias"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Matricula(models.Model):
    PLANOS = (
        ("mensal", "Mensal"),
        ("trimestral", "Trimestral"),
        ("semestral", "Semestral"),
        ("anual", "Anual"),
    )

    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    academia = models.ForeignKey(Academia, on_delete=models.CASCADE)
    data_inicio = models.DateField("Início")
    data_fim = models.DateField("Término")
    plano = models.CharField(max_length=50, choices=PLANOS)
    valor = models.DecimalField("Valor (R$)", max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "matrícula"
        verbose_name_plural = "matrículas"
        ordering = ["-data_inicio", "-id"]

    def __str__(self):
        return f"{self.aluno} - {self.academia}"

    def clean(self):
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            raise ValidationError({"data_fim": "O término não pode ser anterior ao início."})

    @property
    def vigente(self):
        return self.ativa and self.data_fim >= timezone.localdate()

    @property
    def situacao(self):
        if not self.ativa:
            return "Inativa"
        return "Ativa" if self.data_fim >= timezone.localdate() else "Vencida"


# ---------------------------------------------------------------------------
# Treinos
# ---------------------------------------------------------------------------
class Exercicio(models.Model):
    GRUPOS = (
        ("peito", "Peito"),
        ("costas", "Costas"),
        ("ombros", "Ombros"),
        ("biceps", "Bíceps"),
        ("triceps", "Tríceps"),
        ("pernas", "Pernas"),
        ("gluteos", "Glúteos"),
        ("abdomen", "Abdômen"),
        ("cardio", "Cardio"),
        ("outro", "Outro"),
    )

    nome = models.CharField(max_length=100)
    grupo_muscular = models.CharField("Grupo muscular", max_length=100, choices=GRUPOS)
    descricao = models.TextField("Descrição", blank=True)
    video = models.URLField("Vídeo (link)", blank=True)

    class Meta:
        verbose_name = "exercício"
        verbose_name_plural = "exercícios"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Treino(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    treinador = models.ForeignKey(Treinador, on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    descricao = models.TextField("Descrição", blank=True)

    class Meta:
        verbose_name = "treino"
        verbose_name_plural = "treinos"
        ordering = ["-id"]

    def __str__(self):
        return self.nome


class RegistroTreino(models.Model):
    treino = models.ForeignKey(Treino, on_delete=models.CASCADE, related_name="registros")
    exercicio = models.ForeignKey(Exercicio, verbose_name="Exercício", on_delete=models.CASCADE)
    series = models.PositiveSmallIntegerField("Séries", validators=[MinValueValidator(1), MaxValueValidator(50)])
    repeticoes = models.PositiveSmallIntegerField("Repetições", validators=[MinValueValidator(1), MaxValueValidator(500)])
    carga = models.FloatField("Carga (kg)", default=0, validators=[MinValueValidator(0)])

    class Meta:
        verbose_name = "exercício do treino"
        verbose_name_plural = "exercícios do treino"
        ordering = ["id"]

    def __str__(self):
        return self.exercicio.nome


# ---------------------------------------------------------------------------
# Avaliação física
# ---------------------------------------------------------------------------
def _medida(rotulo, maximo=None):
    validadores = [MinValueValidator(0)]
    if maximo is not None:
        validadores.append(MaxValueValidator(maximo))
    return models.FloatField(rotulo, null=True, blank=True, validators=validadores)


class AvaliacaoFisica(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    data = models.DateField()

    # Dados básicos
    peso = models.FloatField("Peso (kg)", validators=[MinValueValidator(20), MaxValueValidator(400)])
    altura = models.FloatField("Altura (m)", validators=[MinValueValidator(0.5), MaxValueValidator(2.8)])
    imc = models.FloatField("IMC", null=True, blank=True, editable=False)
    idade_metabolica = models.PositiveSmallIntegerField(
        "Idade metabólica", null=True, blank=True, validators=[MaxValueValidator(150)]
    )

    # Composição corporal
    percentual_gordura = _medida("Gordura corporal (%)", 100)
    massa_gorda = _medida("Massa gorda (kg)")
    massa_magra = _medida("Massa magra (kg)")
    percentual_muscular = _medida("Massa muscular (%)", 100)
    agua_corporal = _medida("Água corporal (%)", 100)

    # Medidas em centímetros
    pescoco = _medida("Pescoço (cm)")
    ombro = _medida("Ombro (cm)")
    peito = _medida("Peito (cm)")
    cintura = _medida("Cintura (cm)")
    abdomen = _medida("Abdômen (cm)")
    quadril = _medida("Quadril (cm)")
    braco_direito = _medida("Braço direito (cm)")
    braco_esquerdo = _medida("Braço esquerdo (cm)")
    antebraco_direito = _medida("Antebraço direito (cm)")
    antebraco_esquerdo = _medida("Antebraço esquerdo (cm)")
    coxa_direita = _medida("Coxa direita (cm)")
    coxa_esquerda = _medida("Coxa esquerda (cm)")
    panturrilha_direita = _medida("Panturrilha direita (cm)")
    panturrilha_esquerda = _medida("Panturrilha esquerda (cm)")

    class Meta:
        verbose_name = "avaliação física"
        verbose_name_plural = "avaliações físicas"
        ordering = ["-data", "-id"]

    def __str__(self):
        return f"{self.aluno} - {self.data:%d/%m/%Y}"

    def save(self, *args, **kwargs):
        # O IMC é sempre calculado a partir de peso (kg) e altura (m).
        if self.peso and self.altura:
            self.imc = round(self.peso / (self.altura ** 2), 1)
        super().save(*args, **kwargs)

    @property
    def classificacao_imc(self):
        if self.imc is None:
            return ""
        if self.imc < 18.5:
            return "Abaixo do peso"
        if self.imc < 25:
            return "Peso normal"
        if self.imc < 30:
            return "Sobrepeso"
        return "Obesidade"


# ---------------------------------------------------------------------------
# Dieta
# ---------------------------------------------------------------------------
class Dieta(models.Model):
    OBJETIVOS = (
        ("emagrecimento", "Emagrecimento"),
        ("hipertrofia", "Hipertrofia"),
        ("manutencao", "Manutenção"),
        ("saude", "Saúde e bem-estar"),
        ("desempenho", "Desempenho esportivo"),
    )

    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    treinador = models.ForeignKey(Treinador, on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    objetivo = models.CharField(max_length=30, choices=OBJETIVOS)
    calorias_diarias = models.PositiveIntegerField(
        "Meta diária (kcal)", null=True, blank=True, validators=[MaxValueValidator(10000)]
    )
    descricao = models.TextField("Descrição", blank=True)
    criada_em = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "dieta"
        verbose_name_plural = "dietas"
        ordering = ["-criada_em", "-id"]

    def __str__(self):
        return self.nome


class Refeicao(models.Model):
    # A ordem desta lista é a ordem de exibição ao longo do dia.
    TIPOS = (
        ("cafe_manha", "Café da manhã"),
        ("lanche_manha", "Lanche da manhã"),
        ("almoco", "Almoço"),
        ("lanche_tarde", "Lanche da tarde"),
        ("jantar", "Jantar"),
        ("ceia", "Ceia"),
    )

    dieta = models.ForeignKey(Dieta, on_delete=models.CASCADE, related_name="refeicoes")
    tipo = models.CharField("Refeição", max_length=20, choices=TIPOS)
    horario = models.TimeField("Horário", null=True, blank=True)
    alimentos = models.TextField("Alimentos", help_text="Um alimento por linha. Ex.: 2 ovos mexidos")
    calorias = models.PositiveIntegerField("Calorias (kcal)", null=True, blank=True, validators=[MaxValueValidator(5000)])

    class Meta:
        verbose_name = "refeição"
        verbose_name_plural = "refeições"
        ordering = ["id"]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.dieta}"

    @property
    def ordem(self):
        return [codigo for codigo, _ in self.TIPOS].index(self.tipo)


# ---------------------------------------------------------------------------
# Avaliação do treinador e solicitação de troca
# ---------------------------------------------------------------------------
class AvaliacaoTreinador(models.Model):
    NOTAS = (
        (1, "1 - Ruim"),
        (2, "2 - Regular"),
        (3, "3 - Bom"),
        (4, "4 - Muito bom"),
        (5, "5 - Excelente"),
    )

    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    treinador = models.ForeignKey(Treinador, on_delete=models.CASCADE, related_name="avaliacoes_recebidas")
    nota = models.PositiveSmallIntegerField(choices=NOTAS)
    comentario = models.TextField("Comentário", max_length=500, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "avaliação de treinador"
        verbose_name_plural = "avaliações de treinadores"
        ordering = ["-atualizada_em", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["aluno", "treinador"], name="uma_avaliacao_por_aluno_e_treinador"),
        ]

    def __str__(self):
        return f"{self.aluno} → {self.treinador} ({self.nota})"

    @property
    def estrelas(self):
        return "★" * self.nota + "☆" * (5 - self.nota)


class SolicitacaoTroca(models.Model):
    PENDENTE = "pendente"
    APROVADA = "aprovada"
    RECUSADA = "recusada"
    CANCELADA = "cancelada"
    STATUS = (
        (PENDENTE, "Pendente"),
        (APROVADA, "Aprovada"),
        (RECUSADA, "Recusada"),
        (CANCELADA, "Cancelada"),
    )

    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    treinador_atual = models.ForeignKey(
        Treinador, on_delete=models.SET_NULL, null=True, blank=True, related_name="trocas_de_origem"
    )
    treinador_desejado = models.ForeignKey(
        Treinador,
        verbose_name="Treinador desejado (opcional)",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trocas_desejadas",
    )
    motivo = models.TextField("Motivo da solicitação", max_length=500)
    status = models.CharField(max_length=20, choices=STATUS, default=PENDENTE)
    criada_em = models.DateTimeField("Solicitada em", auto_now_add=True)
    resposta = models.TextField("Resposta da administração", blank=True)
    respondida_em = models.DateTimeField(null=True, blank=True)
    respondida_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        verbose_name = "solicitação de troca"
        verbose_name_plural = "solicitações de troca"
        ordering = ["-criada_em", "-id"]

    def __str__(self):
        return f"Troca de treinador - {self.aluno}"

    @property
    def pendente(self):
        return self.status == self.PENDENTE
