from datetime import date, timedelta

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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
from .permissions import usuario_pode
from .validators import validate_cpf

SENHA = "Senha-Forte-123"
CPFS = ["52998224725", "11144477735", "39053344705", "16899535009", "93541134780"]



def criar_admin(username="admin"):
    return User.objects.create_superuser(username, f"{username}@teste.com", SENHA)


def criar_treinador(username="carlos", cpf=CPFS[1]):
    usuario = User.objects.create_user(
        username, f"{username}@teste.com", SENHA, first_name="Carlos", last_name="Silva", tipo=User.TREINADOR
    )
    return Treinador.objects.create(
        user=usuario, cpf=cpf, data_nasc=date(1990, 1, 1), telefone="(84) 99999-1111", endereco="Rua A, 1"
    )


def criar_aluno(username="maria", cpf=CPFS[0], treinador=None):
    usuario = User.objects.create_user(
        username, f"{username}@teste.com", SENHA, first_name="Maria", last_name="Souza", tipo=User.ALUNO
    )
    return Aluno.objects.create(
        user=usuario,
        cpf=cpf,
        data_nasc=date(1995, 5, 20),
        telefone="(84) 98888-2222",
        endereco="Rua B, 2",
        treinador=treinador,
    )


def dados_pessoais(username, cpf, **extra):
    dados = {
        "username": username,
        "first_name": "Joana",
        "last_name": "Lima",
        "email": f"{username}@teste.com",
        "password1": SENHA,
        "password2": SENHA,
        "cpf": cpf,
        "data_nasc": "1998-02-10",
        "telefone": "(84) 97777-3333",
        "endereco": "Rua C, 3",
        "bio": "",
    }
    dados.update(extra)
    return dados


class BaseTest(TestCase):
    def entrar(self, usuario):
        entrou = self.client.login(username=usuario.username, password=SENHA)
        self.assertTrue(entrou)




class ValidadoresPermissoesTests(TestCase):
    def test_cpf(self):
        validate_cpf("529.982.247-25")
        for invalido in ("111.111.111-11", "529.982.247-24", "123"):
            with self.assertRaises(ValidationError):
                validate_cpf(invalido)

    def test_superuser_vira_administrador(self):
        self.assertEqual(criar_admin().tipo, User.ADMINISTRADOR)

    def test_usuario_pode(self):
        admin = criar_admin()
        treinador = criar_treinador().user
        aluno = criar_aluno().user
        self.assertTrue(usuario_pode(admin, "gerenciar_treinadores"))
        self.assertTrue(usuario_pode(treinador, "gerenciar_treinos"))
        self.assertFalse(usuario_pode(treinador, "gerenciar_treinadores"))
        self.assertTrue(usuario_pode(aluno, "ver_treinos"))
        self.assertFalse(usuario_pode(aluno, "gerenciar_treinos"))




class AutenticacaoTests(BaseTest):
    def test_visitante_e_redirecionado_ao_login(self):
        resposta = self.client.get(reverse("index"))
        self.assertRedirects(resposta, f"{reverse('login')}?next={reverse('index')}")

    def test_login_valido(self):
        criar_aluno()
        resposta = self.client.post(reverse("login"), {"username": "maria", "password": SENHA})
        self.assertRedirects(resposta, reverse("index"))

    def test_login_invalido(self):
        criar_aluno()
        resposta = self.client.post(reverse("login"), {"username": "maria", "password": "errada"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "incorretos")

    def test_usuario_inativo_nao_entra(self):
        aluno = criar_aluno()
        aluno.user.is_active = False
        aluno.user.save()
        resposta = self.client.post(reverse("login"), {"username": "maria", "password": SENHA})
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout(self):
        aluno = criar_aluno()
        self.entrar(aluno.user)
        resposta = self.client.post(reverse("logout"))
        self.assertRedirects(resposta, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_cadastro_cria_aluno_e_autentica(self):
        resposta = self.client.post(reverse("cadastro"), dados_pessoais("joana", "529.982.247-25"))
        self.assertRedirects(resposta, reverse("index"))
        usuario = User.objects.get(username="joana")
        self.assertEqual(usuario.tipo, User.ALUNO)
        self.assertTrue(usuario.check_password(SENHA))
        aluno = Aluno.objects.get(user=usuario)
        self.assertEqual(aluno.cpf, "52998224725")  # armazenado só com dígitos
        self.assertIn("_auth_user_id", self.client.session)

    def test_cadastro_rejeita_cpf_invalido(self):
        resposta = self.client.post(reverse("cadastro"), dados_pessoais("joana", "111.111.111-11"))
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(User.objects.filter(username="joana").exists())

    def test_cadastro_rejeita_senhas_diferentes(self):
        resposta = self.client.post(
            reverse("cadastro"), dados_pessoais("joana", CPFS[0], password2="Outra-Senha-456")
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(User.objects.filter(username="joana").exists())

    def test_cadastro_rejeita_usuario_e_cpf_repetidos(self):
        criar_aluno()
        resposta = self.client.post(reverse("cadastro"), dados_pessoais("MARIA", CPFS[1]))
        self.assertEqual(resposta.status_code, 200)  # username repetido (sem diferenciar maiúsculas)
        resposta = self.client.post(reverse("cadastro"), dados_pessoais("joana", CPFS[0]))
        self.assertEqual(resposta.status_code, 200)  # CPF repetido
        self.assertFalse(User.objects.filter(username="joana").exists())

    def test_alterar_senha(self):
        aluno = criar_aluno()
        self.entrar(aluno.user)
        resposta = self.client.post(
            reverse("password_change"),
            {"old_password": SENHA, "new_password1": "Nova-Senha-789", "new_password2": "Nova-Senha-789"},
        )
        self.assertRedirects(resposta, reverse("password_change_done"))
        aluno.user.refresh_from_db()
        self.assertTrue(aluno.user.check_password("Nova-Senha-789"))

    def test_recuperar_senha_envia_email(self):
        criar_aluno()
        resposta = self.client.post(reverse("password_reset"), {"email": "maria@teste.com"})
        self.assertRedirects(resposta, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/reset/", mail.outbox[0].body)

    def test_pagina_inicial_de_cada_perfil(self):
        for usuario in (criar_admin(), criar_treinador().user, criar_aluno().user):
            self.entrar(usuario)
            self.assertEqual(self.client.get(reverse("index")).status_code, 200)
            self.client.logout()




class PermissoesAcessoTests(BaseTest):
    def setUp(self):
        self.admin = criar_admin()
        self.treinador = criar_treinador()
        self.aluno = criar_aluno()

    def status(self, usuario, nome_url, *args):
        self.client.logout()
        self.entrar(usuario)
        return self.client.get(reverse(nome_url, args=args)).status_code

    def test_visitante_vai_para_login(self):
        for nome in ("aluno_list", "treino_list", "avaliacao_list", "exercicio_list", "academia_list"):
            self.assertEqual(self.client.get(reverse(nome)).status_code, 302, nome)

    def test_aluno(self):
        permitidas = ("treino_list", "avaliacao_list", "exercicio_list", "matricula_list", "academia_list", "perfil")
        negadas = ("aluno_list", "aluno_create", "treinador_list", "exercicio_create", "treino_create",
                   "avaliacao_create", "matricula_create", "academia_create")  # fmt: skip
        for nome in permitidas:
            self.assertEqual(self.status(self.aluno.user, nome), 200, nome)
        for nome in negadas:
            self.assertEqual(self.status(self.aluno.user, nome), 403, nome)

    def test_treinador(self):
        permitidas = ("aluno_list", "aluno_create", "exercicio_create", "treino_create", "avaliacao_create", "academia_list")
        negadas = ("treinador_list", "treinador_create", "matricula_list", "academia_create")
        for nome in permitidas:
            self.assertEqual(self.status(self.treinador.user, nome), 200, nome)
        for nome in negadas:
            self.assertEqual(self.status(self.treinador.user, nome), 403, nome)

    def test_treinador_nao_exclui_aluno(self):
        self.assertEqual(self.status(self.treinador.user, "aluno_delete", self.aluno.pk), 403)

    def test_administrador_acessa_tudo(self):
        for nome in ("aluno_list", "treinador_list", "academia_create", "matricula_create", "treino_create"):
            self.assertEqual(self.status(self.admin, nome), 200, nome)


