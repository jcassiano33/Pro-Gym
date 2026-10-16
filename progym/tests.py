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

# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Validadores e permissões
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Permissões de acesso
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# CRUDs
# ---------------------------------------------------------------------------

class CrudAlunoTests(BaseTest):
    def setUp(self):
        self.entrar(criar_admin())

    def test_ciclo_completo(self):
        # criar
        resposta = self.client.post(reverse("aluno_create"), dados_pessoais("joana", "529.982.247-25"))
        self.assertRedirects(resposta, reverse("aluno_list"))
        aluno = Aluno.objects.get(user__username="joana")
        self.assertEqual(aluno.user.tipo, User.ALUNO)

        # listar / buscar / detalhar
        self.assertContains(self.client.get(reverse("aluno_list")), "Joana Lima")
        self.assertContains(self.client.get(reverse("aluno_list"), {"q": "joana"}), "Joana Lima")
        self.assertNotContains(self.client.get(reverse("aluno_list"), {"q": "inexistente"}), "Joana Lima")
        self.assertEqual(self.client.get(reverse("aluno_detail", args=[aluno.pk])).status_code, 200)

        # editar (senha em branco mantém a atual)
        dados = dados_pessoais("joana", CPFS[0], first_name="Joanna", password1="", password2="")
        resposta = self.client.post(reverse("aluno_update", args=[aluno.pk]), dados)
        self.assertRedirects(resposta, reverse("aluno_list"))
        aluno.refresh_from_db()
        self.assertEqual(aluno.user.first_name, "Joanna")
        self.assertTrue(aluno.user.check_password(SENHA))

        # excluir remove o usuário também
        resposta = self.client.post(reverse("aluno_delete", args=[aluno.pk]))
        self.assertRedirects(resposta, reverse("aluno_list"))
        self.assertFalse(Aluno.objects.filter(pk=aluno.pk).exists())
        self.assertFalse(User.objects.filter(username="joana").exists())

    def test_editar_aluno_pode_trocar_senha(self):
        aluno = criar_aluno()
        dados = dados_pessoais("maria", CPFS[0], password1="Nova-Senha-789", password2="Nova-Senha-789")
        self.client.post(reverse("aluno_update", args=[aluno.pk]), dados)
        aluno.user.refresh_from_db()
        self.assertTrue(aluno.user.check_password("Nova-Senha-789"))

    def test_nao_permite_username_repetido(self):
        criar_aluno()
        resposta = self.client.post(reverse("aluno_create"), dados_pessoais("maria", CPFS[1]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(User.objects.filter(username__iexact="maria").count(), 1)


class CrudTreinadorTests(BaseTest):
    def setUp(self):
        self.entrar(criar_admin())

    def test_ciclo_completo(self):
        resposta = self.client.post(reverse("treinador_create"), dados_pessoais("pedro", CPFS[2]))
        self.assertRedirects(resposta, reverse("treinador_list"))
        treinador = Treinador.objects.get(user__username="pedro")
        self.assertEqual(treinador.user.tipo, User.TREINADOR)

        self.assertContains(self.client.get(reverse("treinador_list")), "Joana Lima")
        self.assertEqual(self.client.get(reverse("treinador_detail", args=[treinador.pk])).status_code, 200)

        dados = dados_pessoais("pedro", CPFS[2], first_name="Pedro", password1="", password2="")
        self.client.post(reverse("treinador_update", args=[treinador.pk]), dados)
        treinador.refresh_from_db()
        self.assertEqual(treinador.user.first_name, "Pedro")

        self.client.post(reverse("treinador_delete", args=[treinador.pk]))
        self.assertFalse(Treinador.objects.filter(pk=treinador.pk).exists())
        self.assertFalse(User.objects.filter(username="pedro").exists())


class CrudAcademiaExercicioTests(BaseTest):
    def setUp(self):
        self.entrar(criar_admin())

    def test_academia(self):
        dados = {"nome": "Pro Gym Centro", "endereco": "Rua X, 10", "telefone": "(84) 3333-4444"}
        self.assertRedirects(self.client.post(reverse("academia_create"), dados), reverse("academia_list"))
        academia = Academia.objects.get()
        self.assertContains(self.client.get(reverse("academia_list")), "Pro Gym Centro")
        self.assertEqual(self.client.get(reverse("academia_detail", args=[academia.pk])).status_code, 200)

        dados["nome"] = "Pro Gym Norte"
        self.client.post(reverse("academia_update", args=[academia.pk]), dados)
        academia.refresh_from_db()
        self.assertEqual(academia.nome, "Pro Gym Norte")

        self.client.post(reverse("academia_delete", args=[academia.pk]))
        self.assertFalse(Academia.objects.exists())

    def test_academia_telefone_invalido(self):
        dados = {"nome": "X", "endereco": "Y", "telefone": "123"}
        self.assertEqual(self.client.post(reverse("academia_create"), dados).status_code, 200)
        self.assertFalse(Academia.objects.exists())

    def test_exercicio(self):
        dados = {"nome": "Supino reto", "grupo_muscular": "peito", "descricao": "Peitoral", "video": ""}
        self.assertRedirects(self.client.post(reverse("exercicio_create"), dados), reverse("exercicio_list"))
        exercicio = Exercicio.objects.get()

        self.assertContains(self.client.get(reverse("exercicio_list"), {"grupo": "peito"}), "Supino reto")
        self.assertNotContains(self.client.get(reverse("exercicio_list"), {"grupo": "pernas"}), "Supino reto")
        self.assertEqual(self.client.get(reverse("exercicio_detail", args=[exercicio.pk])).status_code, 200)

        dados["nome"] = "Supino inclinado"
        self.client.post(reverse("exercicio_update", args=[exercicio.pk]), dados)
        exercicio.refresh_from_db()
        self.assertEqual(exercicio.nome, "Supino inclinado")

        self.client.post(reverse("exercicio_delete", args=[exercicio.pk]))
        self.assertFalse(Exercicio.objects.exists())

    def test_exercicio_grupo_invalido(self):
        dados = {"nome": "X", "grupo_muscular": "inexistente", "descricao": "", "video": ""}
        self.assertEqual(self.client.post(reverse("exercicio_create"), dados).status_code, 200)
        self.assertFalse(Exercicio.objects.exists())

class CrudMatriculaTests(BaseTest):
    def setUp(self):
        self.admin = criar_admin()
        self.aluno = criar_aluno()
        self.academia = Academia.objects.create(nome="Pro Gym", endereco="Rua X", telefone="(84) 3333-4444")
        self.entrar(self.admin)
        hoje = timezone.localdate()
        self.dados = {
            "aluno": self.aluno.pk,
            "academia": self.academia.pk,
            "plano": "mensal",
            "data_inicio": hoje.isoformat(),
            "data_fim": (hoje + timedelta(days=30)).isoformat(),
            "valor": "99.90",
            "ativa": "on",
        }

    def test_ciclo_completo(self):
        self.assertRedirects(self.client.post(reverse("matricula_create"), self.dados), reverse("matricula_list"))
        matricula = Matricula.objects.get()
        self.assertTrue(matricula.vigente)
        self.assertContains(self.client.get(reverse("matricula_list")), "Maria Souza")
        self.assertEqual(self.client.get(reverse("matricula_detail", args=[matricula.pk])).status_code, 200)

        self.dados["plano"] = "anual"
        self.client.post(reverse("matricula_update", args=[matricula.pk]), self.dados)
        matricula.refresh_from_db()
        self.assertEqual(matricula.plano, "anual")

        self.client.post(reverse("matricula_delete", args=[matricula.pk]))
        self.assertFalse(Matricula.objects.exists())

    def test_termino_antes_do_inicio_e_rejeitado(self):
        self.dados["data_fim"] = (timezone.localdate() - timedelta(days=5)).isoformat()
        resposta = self.client.post(reverse("matricula_create"), self.dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Matricula.objects.exists())

    def test_aluno_ve_apenas_a_propria_matricula(self):
        outro = criar_aluno("outro", CPFS[3])
        propria = Matricula.objects.create(
            aluno=self.aluno, academia=self.academia, plano="mensal",
            data_inicio=date.today(), data_fim=date.today() + timedelta(days=30), valor=50,
        )  # fmt: skip
        alheia = Matricula.objects.create(
            aluno=outro, academia=self.academia, plano="mensal",
            data_inicio=date.today(), data_fim=date.today() + timedelta(days=30), valor=50,
        )  # fmt: skip
        self.client.logout()
        self.entrar(self.aluno.user)
        self.assertEqual(self.client.get(reverse("matricula_detail", args=[propria.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("matricula_detail", args=[alheia.pk])).status_code, 404)
        self.assertEqual(list(self.client.get(reverse("matricula_list")).context["object_list"]), [propria])


class CrudTreinoTests(BaseTest):
    def setUp(self):
        self.treinador = criar_treinador("carlos", CPFS[1])
        self.outro_treinador = criar_treinador("rafael", CPFS[2])
        self.aluno = criar_aluno(treinador=self.treinador)
        self.exercicio = Exercicio.objects.create(nome="Supino", grupo_muscular="peito")

    def test_treinador_cria_treino_em_seu_nome(self):
        self.entrar(self.treinador.user)
        dados = {"aluno": self.aluno.pk, "nome": "Peito e Tríceps", "descricao": "Treino A"}
        resposta = self.client.post(reverse("treino_create"), dados)
        treino = Treino.objects.get()
        self.assertRedirects(resposta, reverse("treino_detail", args=[treino.pk]))
        self.assertEqual(treino.treinador, self.treinador)

    def test_administrador_escolhe_o_treinador(self):
        self.entrar(criar_admin())
        dados = {"aluno": self.aluno.pk, "treinador": self.outro_treinador.pk, "nome": "Pernas", "descricao": ""}
        self.client.post(reverse("treino_create"), dados)
        self.assertEqual(Treino.objects.get().treinador, self.outro_treinador)

    def test_administrador_precisa_informar_treinador(self):
        self.entrar(criar_admin())
        resposta = self.client.post(reverse("treino_create"), {"aluno": self.aluno.pk, "nome": "Pernas"})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Treino.objects.exists())

    def test_editar_e_excluir_treino(self):
        treino = Treino.objects.create(aluno=self.aluno, treinador=self.treinador, nome="A")
        self.entrar(self.treinador.user)
        dados = {"aluno": self.aluno.pk, "nome": "A renomeado", "descricao": ""}
        self.client.post(reverse("treino_update", args=[treino.pk]), dados)
        treino.refresh_from_db()
        self.assertEqual(treino.nome, "A renomeado")
        self.assertEqual(treino.treinador, self.treinador)

        self.client.post(reverse("treino_delete", args=[treino.pk]))
        self.assertFalse(Treino.objects.exists())

    def test_treinador_nao_mexe_em_treino_alheio(self):
        treino = Treino.objects.create(aluno=self.aluno, treinador=self.treinador, nome="A")
        self.entrar(self.outro_treinador.user)
        self.assertEqual(self.client.get(reverse("treino_detail", args=[treino.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("treino_update", args=[treino.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("treino_delete", args=[treino.pk])).status_code, 404)
        self.assertTrue(Treino.objects.filter(pk=treino.pk).exists())

    def test_aluno_ve_apenas_o_proprio_treino_e_nao_edita(self):
        treino = Treino.objects.create(aluno=self.aluno, treinador=self.treinador, nome="A")
        outro_aluno = criar_aluno("outro", CPFS[3])
        self.entrar(self.aluno.user)
        self.assertEqual(self.client.get(reverse("treino_detail", args=[treino.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("treino_update", args=[treino.pk])).status_code, 403)
        self.client.logout()
        self.entrar(outro_aluno.user)
        self.assertEqual(self.client.get(reverse("treino_detail", args=[treino.pk])).status_code, 404)

    def test_exercicios_do_treino(self):
        treino = Treino.objects.create(aluno=self.aluno, treinador=self.treinador, nome="A")
        self.entrar(self.treinador.user)
        dados = {"exercicio": self.exercicio.pk, "series": 3, "repeticoes": 12, "carga": "20"}

        resposta = self.client.post(reverse("registro_create", args=[treino.pk]), dados)
        self.assertRedirects(resposta, reverse("treino_detail", args=[treino.pk]))
        registro = RegistroTreino.objects.get()
        self.assertEqual(registro.treino, treino)
        self.assertContains(self.client.get(reverse("treino_detail", args=[treino.pk])), "Supino")

        dados["series"] = 4
        self.client.post(reverse("registro_update", args=[registro.pk]), dados)
        registro.refresh_from_db()
        self.assertEqual(registro.series, 4)

        self.client.post(reverse("registro_delete", args=[registro.pk]))
        self.assertFalse(RegistroTreino.objects.exists())

    def test_exercicios_do_treino_alheio_sao_protegidos(self):
        treino = Treino.objects.create(aluno=self.aluno, treinador=self.treinador, nome="A")
        registro = RegistroTreino.objects.create(treino=treino, exercicio=self.exercicio, series=3, repeticoes=10)
        self.entrar(self.outro_treinador.user)
        dados = {"exercicio": self.exercicio.pk, "series": 3, "repeticoes": 12, "carga": "20"}
        self.assertEqual(self.client.post(reverse("registro_create", args=[treino.pk]), dados).status_code, 404)
        self.assertEqual(self.client.post(reverse("registro_update", args=[registro.pk]), dados).status_code, 404)
        self.assertEqual(self.client.post(reverse("registro_delete", args=[registro.pk])).status_code, 404)
        self.assertEqual(RegistroTreino.objects.count(), 1)


class CrudAvaliacaoTests(BaseTest):
    def setUp(self):
        self.treinador = criar_treinador()
        self.aluno = criar_aluno(treinador=self.treinador)
        self.dados = {"aluno": self.aluno.pk, "data": date.today().isoformat(), "peso": "70", "altura": "1.75"}

    def test_ciclo_completo_calcula_imc(self):
        self.entrar(self.treinador.user)
        self.assertRedirects(self.client.post(reverse("avaliacao_create"), self.dados), reverse("avaliacao_list"))
        avaliacao = AvaliacaoFisica.objects.get()
        self.assertEqual(avaliacao.imc, 22.9)
        self.assertEqual(avaliacao.classificacao_imc, "Peso normal")
        self.assertEqual(self.client.get(reverse("avaliacao_detail", args=[avaliacao.pk])).status_code, 200)

        self.dados["peso"] = "90"
        self.client.post(reverse("avaliacao_update", args=[avaliacao.pk]), self.dados)
        avaliacao.refresh_from_db()
        self.assertEqual(avaliacao.imc, 29.4)

        self.client.post(reverse("avaliacao_delete", args=[avaliacao.pk]))
        self.assertFalse(AvaliacaoFisica.objects.exists())

    def test_valores_fora_do_intervalo_sao_rejeitados(self):
        self.entrar(self.treinador.user)
        self.dados["altura"] = "175"  # alguém digitou em centímetros
        self.assertEqual(self.client.post(reverse("avaliacao_create"), self.dados).status_code, 200)
        self.assertFalse(AvaliacaoFisica.objects.exists())

    def test_aluno_ve_apenas_as_proprias_avaliacoes(self):
        outro = criar_aluno("outro", CPFS[3])
        propria = AvaliacaoFisica.objects.create(aluno=self.aluno, data=date.today(), peso=70, altura=1.75)
        alheia = AvaliacaoFisica.objects.create(aluno=outro, data=date.today(), peso=80, altura=1.80)
        self.entrar(self.aluno.user)
        self.assertEqual(list(self.client.get(reverse("avaliacao_list")).context["object_list"]), [propria])
        self.assertEqual(self.client.get(reverse("avaliacao_detail", args=[alheia.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("avaliacao_update", args=[propria.pk])).status_code, 403)


class PerfilTests(BaseTest):
    def test_aluno_edita_o_proprio_perfil(self):
        aluno = criar_aluno()
        self.entrar(aluno.user)
        self.assertEqual(self.client.get(reverse("perfil")).status_code, 200)
        dados = {
            "first_name": "Mariana",
            "last_name": "Souza",
            "email": "mariana@teste.com",
            "data_nasc": "1995-05-20",
            "telefone": "(84) 91111-2222",
            "endereco": "Rua Nova, 9",
            "bio": "Treino 5x por semana",
        }
        self.assertRedirects(self.client.post(reverse("perfil"), dados), reverse("perfil"))
        aluno.refresh_from_db()
        self.assertEqual(aluno.user.first_name, "Mariana")
        self.assertEqual(aluno.telefone, "(84) 91111-2222")

    def test_administrador_edita_apenas_dados_de_usuario(self):
        admin = criar_admin()
        self.entrar(admin)
        dados = {"first_name": "Admin", "last_name": "Geral", "email": "admin@teste.com"}
        self.assertRedirects(self.client.post(reverse("perfil"), dados), reverse("perfil"))
        admin.refresh_from_db()
        self.assertEqual(admin.first_name, "Admin")


# ---------------------------------------------------------------------------
# Dieta
# ---------------------------------------------------------------------------
class CrudDietaTests(BaseTest):
    def setUp(self):
        self.treinador = criar_treinador("carlos", CPFS[1])
        self.outro_treinador = criar_treinador("rafael", CPFS[2])
        self.aluno = criar_aluno(treinador=self.treinador)
        self.dados = {
            "aluno": self.aluno.pk,
            "nome": "Plano de ganho",
            "objetivo": "hipertrofia",
            "calorias_diarias": "2500",
            "descricao": "",
        }

    def test_treinador_cria_dieta_em_seu_nome(self):
        self.entrar(self.treinador.user)
        resposta = self.client.post(reverse("dieta_create"), self.dados)
        dieta = Dieta.objects.get()
        self.assertRedirects(resposta, reverse("dieta_detail", args=[dieta.pk]))
        self.assertEqual(dieta.treinador, self.treinador)

    def test_administrador_escolhe_o_treinador(self):
        self.entrar(criar_admin())
        self.client.post(reverse("dieta_create"), {**self.dados, "treinador": self.outro_treinador.pk})
        self.assertEqual(Dieta.objects.get().treinador, self.outro_treinador)
        self.assertEqual(self.client.post(reverse("dieta_create"), self.dados).status_code, 200)
        self.assertEqual(Dieta.objects.count(), 1)

    def test_editar_e_excluir(self):
        dieta = Dieta.objects.create(aluno=self.aluno, treinador=self.treinador, nome="A", objetivo="saude")
        self.entrar(self.treinador.user)
        self.client.post(reverse("dieta_update", args=[dieta.pk]), {**self.dados, "nome": "Renomeada"})
        dieta.refresh_from_db()
        self.assertEqual(dieta.nome, "Renomeada")
        self.assertEqual(dieta.treinador, self.treinador)
        self.assertContains(self.client.get(reverse("dieta_list")), "Renomeada")
        self.client.post(reverse("dieta_delete", args=[dieta.pk]))
        self.assertFalse(Dieta.objects.exists())

    def test_escopo_por_perfil(self):
        dieta = Dieta.objects.create(aluno=self.aluno, treinador=self.treinador, nome="A", objetivo="saude")
        outro_aluno = criar_aluno("outro", CPFS[3])
        # aluno dono vê, mas não edita
        self.entrar(self.aluno.user)
        self.assertEqual(self.client.get(reverse("dieta_detail", args=[dieta.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("dieta_update", args=[dieta.pk])).status_code, 403)
        # outro aluno e outro treinador não enxergam
        self.client.logout()
        self.entrar(outro_aluno.user)
        self.assertEqual(self.client.get(reverse("dieta_detail", args=[dieta.pk])).status_code, 404)
        self.client.logout()
        self.entrar(self.outro_treinador.user)
        self.assertEqual(self.client.get(reverse("dieta_detail", args=[dieta.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("dieta_delete", args=[dieta.pk])).status_code, 404)

    def test_refeicoes(self):
        dieta = Dieta.objects.create(aluno=self.aluno, treinador=self.treinador, nome="A", objetivo="saude")
        self.entrar(self.treinador.user)
        dados = {"tipo": "cafe_manha", "horario": "07:30", "alimentos": "Ovos\nPão integral", "calorias": "400"}

        resposta = self.client.post(reverse("refeicao_create", args=[dieta.pk]), dados)
        self.assertRedirects(resposta, reverse("dieta_detail", args=[dieta.pk]))
        refeicao = Refeicao.objects.get()
        self.assertEqual(refeicao.dieta, dieta)
        self.assertContains(self.client.get(reverse("dieta_detail", args=[dieta.pk])), "Pão integral")

        self.client.post(reverse("refeicao_update", args=[refeicao.pk]), {**dados, "tipo": "almoco"})
        refeicao.refresh_from_db()
        self.assertEqual(refeicao.tipo, "almoco")

        self.client.post(reverse("refeicao_delete", args=[refeicao.pk]))
        self.assertFalse(Refeicao.objects.exists())

    def test_refeicoes_de_dieta_alheia_sao_protegidas(self):
        dieta = Dieta.objects.create(aluno=self.aluno, treinador=self.treinador, nome="A", objetivo="saude")
        refeicao = Refeicao.objects.create(dieta=dieta, tipo="jantar", alimentos="Sopa")
        self.entrar(self.outro_treinador.user)
        dados = {"tipo": "almoco", "alimentos": "X"}
        self.assertEqual(self.client.post(reverse("refeicao_create", args=[dieta.pk]), dados).status_code, 404)
        self.assertEqual(self.client.post(reverse("refeicao_update", args=[refeicao.pk]), dados).status_code, 404)
        self.assertEqual(self.client.post(reverse("refeicao_delete", args=[refeicao.pk])).status_code, 404)
        self.assertEqual(Refeicao.objects.count(), 1)


# ---------------------------------------------------------------------------
# Avaliar treinador
# ---------------------------------------------------------------------------
class AvaliarTreinadorTests(BaseTest):
    def setUp(self):
        self.treinador = criar_treinador("carlos", CPFS[1])
        self.aluno = criar_aluno(treinador=self.treinador)

    def test_pagina_meu_treinador(self):
        self.entrar(self.aluno.user)
        resposta = self.client.get(reverse("meu_treinador"))
        self.assertContains(resposta, "Carlos Silva")
        self.assertContains(resposta, "Avaliar treinador")

    def test_pagina_meu_treinador_so_para_alunos(self):
        self.entrar(criar_admin())
        self.assertEqual(self.client.get(reverse("meu_treinador")).status_code, 403)
        self.client.logout()
        self.entrar(self.treinador.user)
        self.assertEqual(self.client.get(reverse("avaliar_treinador")).status_code, 403)

    def test_avaliar_e_alterar_mantem_uma_unica_avaliacao(self):
        self.entrar(self.aluno.user)
        resposta = self.client.post(reverse("avaliar_treinador"), {"nota": "5", "comentario": "Ótimo"})
        self.assertRedirects(resposta, reverse("meu_treinador"))
        avaliacao = AvaliacaoTreinador.objects.get()
        self.assertEqual((avaliacao.nota, avaliacao.treinador, avaliacao.aluno), (5, self.treinador, self.aluno))
        self.assertEqual(avaliacao.estrelas, "★★★★★")

        self.client.post(reverse("avaliar_treinador"), {"nota": "3", "comentario": "Mudei de ideia"})
        self.assertEqual(AvaliacaoTreinador.objects.count(), 1)
        avaliacao.refresh_from_db()
        self.assertEqual(avaliacao.nota, 3)
        self.assertContains(self.client.get(reverse("meu_treinador")), "Alterar minha avaliação")

    def test_nota_invalida_e_rejeitada(self):
        self.entrar(self.aluno.user)
        for nota in ("0", "6", "", "abc"):
            self.assertEqual(self.client.post(reverse("avaliar_treinador"), {"nota": nota}).status_code, 200)
        self.assertFalse(AvaliacaoTreinador.objects.exists())

    def test_aluno_sem_treinador_nao_avalia(self):
        sem_treinador = criar_aluno("solto", CPFS[3])
        self.entrar(sem_treinador.user)
        resposta = self.client.post(reverse("avaliar_treinador"), {"nota": "5"})
        self.assertRedirects(resposta, reverse("meu_treinador"))
        self.assertFalse(AvaliacaoTreinador.objects.exists())

    def test_quem_enxerga_cada_avaliacao(self):
        outro_treinador = criar_treinador("rafael", CPFS[2])
        outro_aluno = criar_aluno("outro", CPFS[3], treinador=outro_treinador)
        minha = AvaliacaoTreinador.objects.create(aluno=self.aluno, treinador=self.treinador, nota=4)
        alheia = AvaliacaoTreinador.objects.create(aluno=outro_aluno, treinador=outro_treinador, nota=2)

        def lista():
            return list(self.client.get(reverse("avaliacao_treinador_list")).context["object_list"])

        self.entrar(self.treinador.user)  # treinador vê só as que recebeu
        self.assertEqual(lista(), [minha])
        self.client.logout()
        self.entrar(self.aluno.user)  # aluno vê só a que fez
        self.assertEqual(lista(), [minha])
        self.client.logout()
        self.entrar(criar_admin())  # administrador vê todas
        self.assertEqual(set(lista()), {minha, alheia})

    def test_apenas_administrador_exclui_avaliacao(self):
        avaliacao = AvaliacaoTreinador.objects.create(aluno=self.aluno, treinador=self.treinador, nota=1)
        self.entrar(self.aluno.user)
        self.assertEqual(self.client.post(reverse("avaliacao_treinador_delete", args=[avaliacao.pk])).status_code, 403)
        self.client.logout()
        self.entrar(criar_admin())
        self.assertRedirects(
            self.client.post(reverse("avaliacao_treinador_delete", args=[avaliacao.pk])),
            reverse("avaliacao_treinador_list"),
        )
        self.assertFalse(AvaliacaoTreinador.objects.exists())


# ---------------------------------------------------------------------------
# Solicitar troca de treinador
# ---------------------------------------------------------------------------
class TrocaTreinadorTests(BaseTest):
    def setUp(self):
        self.atual = criar_treinador("carlos", CPFS[1])
        self.novo = criar_treinador("rafael", CPFS[2])
        self.aluno = criar_aluno(treinador=self.atual)
        self.admin = criar_admin()

    def solicitar(self, **extra):
        dados = {"treinador_desejado": self.novo.pk, "motivo": "Horários incompatíveis"}
        dados.update(extra)
        return self.client.post(reverse("troca_create"), dados)

    def test_aluno_solicita_troca(self):
        self.entrar(self.aluno.user)
        self.assertEqual(self.client.get(reverse("troca_create")).status_code, 200)
        self.assertRedirects(self.solicitar(), reverse("troca_list"))
        troca = SolicitacaoTroca.objects.get()
        self.assertEqual(troca.aluno, self.aluno)
        self.assertEqual(troca.treinador_atual, self.atual)
        self.assertEqual(troca.treinador_desejado, self.novo)
        self.assertEqual(troca.status, SolicitacaoTroca.PENDENTE)
        self.assertContains(self.client.get(reverse("troca_list")), "Pendente")
        self.assertContains(self.client.get(reverse("meu_treinador")), "ver andamento")

    def test_motivo_e_obrigatorio_e_preferencia_e_opcional(self):
        self.entrar(self.aluno.user)
        self.assertEqual(self.solicitar(motivo="").status_code, 200)
        self.assertFalse(SolicitacaoTroca.objects.exists())
        self.assertRedirects(self.solicitar(treinador_desejado=""), reverse("troca_list"))
        self.assertIsNone(SolicitacaoTroca.objects.get().treinador_desejado)

    def test_nao_aceita_o_proprio_treinador_atual_como_desejado(self):
        self.entrar(self.aluno.user)
        self.assertEqual(self.solicitar(treinador_desejado=self.atual.pk).status_code, 200)
        self.assertFalse(SolicitacaoTroca.objects.exists())

    def test_apenas_uma_solicitacao_pendente_por_vez(self):
        self.entrar(self.aluno.user)
        self.solicitar()
        self.assertEqual(self.solicitar().status_code, 200)
        self.assertEqual(SolicitacaoTroca.objects.count(), 1)

    def test_administrador_e_treinador_nao_solicitam(self):
        self.entrar(self.admin)
        self.assertEqual(self.client.get(reverse("troca_create")).status_code, 403)
        self.client.logout()
        self.entrar(self.atual.user)
        self.assertEqual(self.client.get(reverse("troca_create")).status_code, 403)

    def test_administrador_aprova_e_o_treinador_do_aluno_muda(self):
        self.entrar(self.aluno.user)
        self.solicitar()
        troca = SolicitacaoTroca.objects.get()
        self.client.logout()

        self.entrar(self.admin)
        self.assertContains(self.client.get(reverse("troca_detail", args=[troca.pk])), "Responder solicitação")
        resposta = self.client.post(
            reverse("troca_responder", args=[troca.pk]),
            {"decisao": "aprovada", "novo_treinador": self.novo.pk, "resposta": "Combinado!"},
        )
        self.assertRedirects(resposta, reverse("troca_detail", args=[troca.pk]))
        troca.refresh_from_db()
        self.aluno.refresh_from_db()
        self.assertEqual(troca.status, SolicitacaoTroca.APROVADA)
        self.assertEqual(troca.respondida_por, self.admin)
        self.assertIsNotNone(troca.respondida_em)
        self.assertEqual(self.aluno.treinador, self.novo)

        # já respondida: uma segunda resposta é ignorada
        self.client.post(reverse("troca_responder", args=[troca.pk]), {"decisao": "recusada"})
        troca.refresh_from_db()
        self.assertEqual(troca.status, SolicitacaoTroca.APROVADA)

    def test_aprovar_sem_novo_treinador_nao_faz_nada(self):
        troca = SolicitacaoTroca.objects.create(aluno=self.aluno, treinador_atual=self.atual, motivo="x")
        self.entrar(self.admin)
        self.client.post(reverse("troca_responder", args=[troca.pk]), {"decisao": "aprovada"})
        troca.refresh_from_db()
        self.aluno.refresh_from_db()
        self.assertEqual(troca.status, SolicitacaoTroca.PENDENTE)
        self.assertEqual(self.aluno.treinador, self.atual)

    def test_recusar_mantem_o_treinador(self):
        troca = SolicitacaoTroca.objects.create(aluno=self.aluno, treinador_atual=self.atual, motivo="x")
        self.entrar(self.admin)
        self.client.post(reverse("troca_responder", args=[troca.pk]), {"decisao": "recusada", "resposta": "Não agora"})
        troca.refresh_from_db()
        self.aluno.refresh_from_db()
        self.assertEqual(troca.status, SolicitacaoTroca.RECUSADA)
        self.assertEqual(troca.resposta, "Não agora")
        self.assertEqual(self.aluno.treinador, self.atual)

    def test_aluno_sem_treinador_pode_pedir_um(self):
        sem_treinador = criar_aluno("solto", CPFS[3])
        self.entrar(sem_treinador.user)
        self.assertRedirects(self.solicitar(), reverse("troca_list"))
        self.assertIsNone(SolicitacaoTroca.objects.get().treinador_atual)

    def test_aluno_nao_responde_solicitacao(self):
        troca = SolicitacaoTroca.objects.create(aluno=self.aluno, treinador_atual=self.atual, motivo="x")
        self.entrar(self.aluno.user)
        resposta = self.client.post(
            reverse("troca_responder", args=[troca.pk]), {"decisao": "aprovada", "novo_treinador": self.novo.pk}
        )
        self.assertEqual(resposta.status_code, 403)
        self.aluno.refresh_from_db()
        self.assertEqual(self.aluno.treinador, self.atual)

    def test_aluno_cancela_a_propria_solicitacao(self):
        troca = SolicitacaoTroca.objects.create(aluno=self.aluno, treinador_atual=self.atual, motivo="x")
        self.entrar(self.aluno.user)
        self.assertRedirects(self.client.post(reverse("troca_cancelar", args=[troca.pk])), reverse("troca_detail", args=[troca.pk]))
        troca.refresh_from_db()
        self.assertEqual(troca.status, SolicitacaoTroca.CANCELADA)
        # depois de cancelada, é possível fazer uma nova
        self.assertRedirects(self.solicitar(), reverse("troca_list"))

    def test_escopo_de_visualizacao(self):
        troca = SolicitacaoTroca.objects.create(aluno=self.aluno, treinador_atual=self.atual, motivo="x")
        outro_aluno = criar_aluno("outro", CPFS[3])

        self.entrar(self.atual.user)  # treinador atual enxerga
        self.assertEqual(self.client.get(reverse("troca_detail", args=[troca.pk])).status_code, 200)
        self.client.logout()
        self.entrar(self.novo.user)  # outro treinador não
        self.assertEqual(self.client.get(reverse("troca_detail", args=[troca.pk])).status_code, 404)
        self.client.logout()
        self.entrar(outro_aluno.user)  # nem outro aluno, que também não consegue cancelar
        self.assertEqual(self.client.get(reverse("troca_detail", args=[troca.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("troca_cancelar", args=[troca.pk])).status_code, 404)
        troca.refresh_from_db()
        self.assertEqual(troca.status, SolicitacaoTroca.PENDENTE)


class PainelNovasFuncionalidadesTests(BaseTest):
    def test_paineis_e_menus_renderizam_para_todos_os_perfis(self):
        treinador = criar_treinador("carlos", CPFS[1])
        aluno = criar_aluno(treinador=treinador)
        Dieta.objects.create(aluno=aluno, treinador=treinador, nome="Dieta A", objetivo="saude")
        AvaliacaoTreinador.objects.create(aluno=aluno, treinador=treinador, nota=5)
        for usuario in (criar_admin(), treinador.user, aluno.user):
            self.entrar(usuario)
            resposta = self.client.get(reverse("index"))
            self.assertEqual(resposta.status_code, 200)
            self.assertContains(resposta, reverse("dieta_list"))
            self.client.logout()

    def test_painel_do_aluno_mostra_a_dieta(self):
        treinador = criar_treinador("carlos", CPFS[1])
        aluno = criar_aluno(treinador=treinador)
        Dieta.objects.create(aluno=aluno, treinador=treinador, nome="Dieta A", objetivo="saude")
        self.entrar(aluno.user)
        self.assertContains(self.client.get(reverse("index")), "Dieta A")

    def test_painel_do_treinador_mostra_a_nota_media(self):
        treinador = criar_treinador("carlos", CPFS[1])
        aluno = criar_aluno(treinador=treinador)
        AvaliacaoTreinador.objects.create(aluno=aluno, treinador=treinador, nota=4)
        self.entrar(treinador.user)
        self.assertContains(self.client.get(reverse("index")), "4,0")