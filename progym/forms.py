from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    Academia,
    Aluno,
    AvaliacaoFisica,
    AvaliacaoTreinador,
    Dieta,
    Exercicio,
    Matricula,
    RegistroTreino,
    Refeicao,
    SolicitacaoTroca,
    Treinador,
    Treino,
    User,
)
from .validators import somente_digitos, validate_nome


# ---------------------------------------------------------------------------
# Base visual (Bootstrap) para todos os formulários
# ---------------------------------------------------------------------------
class BootstrapFormMixin:
    """Aplica as classes do Bootstrap aos widgets e marca campos com erro."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                classe = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                classe = "form-select"
            else:
                classe = "form-control"
            existente = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existente} {classe}".strip()

    def full_clean(self):
        super().full_clean()
        if self.is_bound:
            for nome in self.errors:
                if nome in self.fields:
                    widget = self.fields[nome].widget
                    widget.attrs["class"] = widget.attrs.get("class", "") + " is-invalid"


def _data():
    return forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------
class LoginForm(BootstrapFormMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Usuário"
        self.fields["username"].widget.attrs.update({"placeholder": "Seu usuário", "autofocus": True})
        self.fields["password"].label = "Senha"
        self.fields["password"].widget.attrs.update({"placeholder": "Sua senha"})
        self.error_messages = {
            **self.error_messages,
            "invalid_login": "Usuário ou senha incorretos. Verifique e tente novamente.",
        }


class SenhaAlteracaoForm(BootstrapFormMixin, PasswordChangeForm):
    pass


class RecuperarSenhaForm(BootstrapFormMixin, PasswordResetForm):
    pass


class NovaSenhaForm(BootstrapFormMixin, SetPasswordForm):
    pass


# ---------------------------------------------------------------------------
# Usuário + perfil (Aluno / Treinador): cria/edita o User junto com o perfil
# ---------------------------------------------------------------------------
_WIDGETS_PERFIL = {
    "cpf": forms.TextInput(attrs={"data-mask": "cpf", "placeholder": "000.000.000-00"}),
    "data_nasc": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    "telefone": forms.TextInput(attrs={"data-mask": "telefone", "placeholder": "(84) 99999-9999"}),
    "bio": forms.Textarea(attrs={"rows": 3}),
}


class UsuarioPerfilForm(BootstrapFormMixin, forms.ModelForm):
    """Base para Aluno/Treinador: além dos campos do perfil, edita os dados de login."""

    tipo_usuario = None  # definido nas subclasses

    username = forms.CharField(
        label="Usuário",
        max_length=150,
        validators=[UnicodeUsernameValidator()],
        help_text="Letras, números e @/./+/-/_",
    )
    first_name = forms.CharField(label="Nome", max_length=150, validators=[validate_nome])
    last_name = forms.CharField(label="Sobrenome", max_length=150, validators=[validate_nome])
    email = forms.EmailField(label="E-mail")
    password1 = forms.CharField(
        label="Senha",
        strip=False,
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirmação da senha",
        strip=False,
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance")
        self.editando = instance is not None and instance.pk is not None
        if self.editando:
            usuario = instance.user
            inicial = dict(kwargs.get("initial") or {})
            inicial.update(
                username=usuario.username,
                first_name=usuario.first_name,
                last_name=usuario.last_name,
                email=usuario.email,
            )
            kwargs["initial"] = inicial
        super().__init__(*args, **kwargs)

        if self.editando:
            self.fields["password1"].help_text = "Deixe em branco para manter a senha atual."
        else:
            self.fields["password1"].required = True
            self.fields["password2"].required = True

        if "treinador" in self.fields:
            self.fields["treinador"].queryset = Treinador.objects.select_related("user").order_by(
                "user__first_name", "user__username"
            )
            self.fields["treinador"].empty_label = "Sem treinador"

    def _usuario_id(self):
        return self.instance.user_id if self.editando else None

    def clean_username(self):
        username = self.cleaned_data["username"]
        existe = User.objects.filter(username__iexact=username).exclude(pk=self._usuario_id()).exists()
        if existe:
            raise ValidationError("Este nome de usuário já está em uso.")
        return username

    def clean_cpf(self):
        return somente_digitos(self.cleaned_data["cpf"])

    def clean(self):
        dados = super().clean()
        senha1 = dados.get("password1")
        senha2 = dados.get("password2")
        if senha1 or senha2:
            if senha1 != senha2:
                self.add_error("password2", "As senhas não conferem.")
            else:
                temporario = User(
                    username=dados.get("username", ""),
                    first_name=dados.get("first_name", ""),
                    last_name=dados.get("last_name", ""),
                    email=dados.get("email", ""),
                )
                try:
                    validate_password(senha1, temporario)
                except ValidationError as erro:
                    self.add_error("password1", erro)
        return dados

    @transaction.atomic
    def save(self, commit=True):
        """Salva usuário e perfil juntos (sempre grava; `commit` é ignorado)."""
        dados = self.cleaned_data
        perfil = super().save(commit=False)
        usuario = perfil.user if perfil.pk else User(tipo=self.tipo_usuario)
        usuario.username = dados["username"]
        usuario.first_name = dados["first_name"]
        usuario.last_name = dados["last_name"]
        usuario.email = dados["email"]
        if dados.get("password1"):
            usuario.set_password(dados["password1"])
        usuario.save()
        perfil.user = usuario
        perfil.save()
        return perfil


class TreinadorForm(UsuarioPerfilForm):
    tipo_usuario = User.TREINADOR

    class Meta:
        model = Treinador
        fields = ["cpf", "data_nasc", "telefone", "endereco", "foto", "bio"]
        widgets = _WIDGETS_PERFIL


class AlunoForm(UsuarioPerfilForm):
    tipo_usuario = User.ALUNO

    class Meta:
        model = Aluno
        fields = ["cpf", "data_nasc", "telefone", "endereco", "treinador", "foto", "bio"]
        widgets = _WIDGETS_PERFIL


class CadastroForm(AlunoForm):
    """Auto-cadastro público de aluno (sem escolher treinador nem enviar foto)."""

    class Meta(AlunoForm.Meta):
        fields = ["cpf", "data_nasc", "telefone", "endereco"]


# ---------------------------------------------------------------------------
# "Meu perfil": o próprio usuário edita seus dados
# ---------------------------------------------------------------------------
class MeuUsuarioForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        labels = {"first_name": "Nome", "last_name": "Sobrenome", "email": "E-mail"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome in ("first_name", "last_name"):
            self.fields[nome].required = True
            self.fields[nome].validators.append(validate_nome)
        self.fields["email"].required = True


class MeuPerfilAlunoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Aluno
        fields = ["data_nasc", "telefone", "endereco", "foto", "bio"]
        widgets = _WIDGETS_PERFIL


class MeuPerfilTreinadorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Treinador
        fields = ["data_nasc", "telefone", "endereco", "foto", "bio"]
        widgets = _WIDGETS_PERFIL


# ---------------------------------------------------------------------------
# Demais CRUDs
# ---------------------------------------------------------------------------
class AcademiaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Academia
        fields = ["nome", "endereco", "telefone"]
        widgets = {"telefone": forms.TextInput(attrs={"data-mask": "telefone", "placeholder": "(84) 3333-3333"})}


def _ordenar_alunos(campo):
    campo.queryset = Aluno.objects.select_related("user").order_by("user__first_name", "user__username")


class MatriculaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Matricula
        fields = ["aluno", "academia", "plano", "data_inicio", "data_fim", "valor", "ativa"]
        widgets = {"data_inicio": _data(), "data_fim": _data()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _ordenar_alunos(self.fields["aluno"])
        if not self.is_bound and not self.instance.pk:
            self.fields["data_inicio"].initial = timezone.localdate()


class ExercicioForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Exercicio
        fields = ["nome", "grupo_muscular", "descricao", "video"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 3})}


class TreinoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Treino
        fields = ["aluno", "treinador", "nome", "descricao"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        _ordenar_alunos(self.fields["aluno"])
        self.fields["treinador"].queryset = Treinador.objects.select_related("user").order_by(
            "user__first_name", "user__username"
        )
        # Treinador comum cria treinos sempre em seu próprio nome.
        if user is not None and not user.is_administrador:
            del self.fields["treinador"]


class RegistroTreinoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RegistroTreino
        fields = ["exercicio", "series", "repeticoes", "carga"]


class AvaliacaoFisicaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AvaliacaoFisica
        fields = "__all__"
        widgets = {"data": _data()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _ordenar_alunos(self.fields["aluno"])
        if not self.is_bound and not self.instance.pk:
            self.fields["data"].initial = timezone.localdate()


# ---------------------------------------------------------------------------
# Dieta
# ---------------------------------------------------------------------------
def _ordenar_treinadores(campo):
    campo.queryset = Treinador.objects.select_related("user").order_by("user__first_name", "user__username")


class DietaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Dieta
        fields = ["aluno", "treinador", "nome", "objetivo", "calorias_diarias", "descricao"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        _ordenar_alunos(self.fields["aluno"])
        _ordenar_treinadores(self.fields["treinador"])
        # Treinador comum cria dietas sempre em seu próprio nome.
        if user is not None and not user.is_administrador:
            del self.fields["treinador"]


class RefeicaoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Refeicao
        fields = ["tipo", "horario", "alimentos", "calorias"]
        widgets = {
            "horario": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "alimentos": forms.Textarea(attrs={"rows": 4}),
        }


# ---------------------------------------------------------------------------
# Avaliar treinador / solicitar troca
# ---------------------------------------------------------------------------
class AvaliacaoTreinadorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AvaliacaoTreinador
        fields = ["nota", "comentario"]
        widgets = {"comentario": forms.Textarea(attrs={"rows": 4, "placeholder": "Conte como tem sido o acompanhamento (opcional)"})}


class SolicitacaoTrocaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SolicitacaoTroca
        fields = ["treinador_desejado", "motivo"]
        widgets = {"motivo": forms.Textarea(attrs={"rows": 4, "placeholder": "Explique por que deseja trocar de treinador"})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        _ordenar_treinadores(self.fields["treinador_desejado"])
        self.fields["treinador_desejado"].empty_label = "Sem preferência"
        aluno = user.perfil_aluno if user is not None else None
        if aluno is not None and aluno.treinador_id:
            self.fields["treinador_desejado"].queryset = self.fields["treinador_desejado"].queryset.exclude(
                pk=aluno.treinador_id
            )


class RespostaTrocaForm(BootstrapFormMixin, forms.Form):
    """Resposta da administração a uma solicitação de troca."""

    DECISOES = (
        ("aprovada", "Aprovar troca"),
        ("recusada", "Recusar solicitação"),
    )

    decisao = forms.ChoiceField(label="Decisão", choices=DECISOES)
    novo_treinador = forms.ModelChoiceField(
        label="Novo treinador (obrigatório ao aprovar)",
        queryset=Treinador.objects.none(),
        required=False,
        empty_label="Selecione",
    )
    resposta = forms.CharField(
        label="Mensagem para o aluno",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _ordenar_treinadores(self.fields["novo_treinador"])

    def clean(self):
        dados = super().clean()
        if dados.get("decisao") == "aprovada" and not dados.get("novo_treinador"):
            self.add_error("novo_treinador", "Escolha o novo treinador para aprovar a troca.")
        return dados
