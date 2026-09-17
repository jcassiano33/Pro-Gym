from django import forms
from .models import Mensagem, Post, User
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit
from django.contrib.auth.forms import UserCreationForm as DjangoUserCreationForm
from django.contrib.auth.forms import UsernameField


class UserCreationForm(DjangoUserCreationForm):
    class Meta:
        model = User
        fields = ("username",)
        field_class = {"username": UsernameFierld}

class MensagemForm(forms.ModelForm):
    class Meta:
        model = Mensagem
        fields = "__all__"

class ProForm(forms.ModelForm):

    class Meta:
        model = Post
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('titulo', css_class='col-md-6'),
                Column('autor', css_class='col-md-6'),
                css_class='row'
            ),
            Row(
                Column('imagem', css_class='col-12'),
                css_class='row'
            ),
            Row(
                Column('texto', css_class='col-12'),
                css_class='row'
            ),
            Submit('submit', 'Enviar', css_class='btn btn-primary')
        )