from django.shortcuts import render, get_object_or_404, redirect
from .models import Mensagem, Blog, Exercicio
from .forms import MensagemForm, PostForm, UserCreationForm
from django.contrib.auth.decorators import login_required, permission_required


def index(request):

    context = {
        "exercicios": Exercicio.objects.all(),
        "titulo_blog":  Blog.objects.first().titulo
    }
    return render(request, "progym/index.html", context)

def cadastro(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = UserCreationForm()
        
@login_required
@permission_required("progym.view_exercicio")
def exercicios(request, id_exercicio):
    context = {
        "post": get_object_or_404(Exercicio, id=id_exercicio),
    }
    return render(request, "progym/exercicio.html", context)

@login_required
@permission_required("progym.add_exercicio")
def novo_exercicio(request):
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect("index")
    else:
        form = PostForm()

    context = {
        "form": form,
    }
    return render(request, "progym/form_exercicio.html", context)

@login_required
@permission_required("progym.change_exercicio")
def editar_exercicio(request, id_exercicio):
    post = get_object_or_404(Exercicio, id=id_exercicio)
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            return redirect("index")
    else:
        form = PostForm(instance=post)

    context = {
        "form": form,
        "is_editar": True,
    }
    return render(request, "progym/form_post.html", context)

@login_required
@permission_required("progym.delete_exercicio")
def remover_exercicio(request, id_exercicio):
    if request.method == "POST":
        post = get_object_or_404(Exercicio, id=id_exercicio)
        post.delete()
        return redirect("index")
    else:
        return render(request, "progym/confirmar_remocao.html")
    
@login_required
def perfil(request):
    return render(request, "registration/perfil.html")