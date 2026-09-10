from django.shortcuts import render, get_object_or_404, redirect
from .models import Post, Mensagem, Blog
from .forms import MensagemForm, PostForm
from django.contrib.auth.decorators import login_required, permission_required


def index(request):

    context = {
        "posts": Post.objects.all(),
        "titulo_blog": Blog.objects.first().titulo
    }
    return render(request, "progym/index.html", context)

@login_required
@permission_required("blog.view_post")
def posts(request, id_post):
    context = {
        "post": get_object_or_404(Post, id=id_post),
    }
    return render(request, "progym/post.html", context)

@login_required
@permission_required("blog.add_post")
def novo_post(request):
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
    return render(request, "progym/form_post.html", context)

@login_required
@permission_required("blog.change_post")
def editar_post(request, id_post):
    post = get_object_or_404(Post, id=id_post)
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
@permission_required("blog.delete_post")
def remover_post(request, id_post):
    if request.method == "POST":
        post = get_object_or_404(Post, id=id_post)
        post.delete()
        return redirect("index")
    else:
        return render(request, "progym/confirmar_remocao.html")

@login_required
def contato(request):
    if request.method == "POST":
        form = MensagemForm(request.POST)
        if form.is_valid():
            form.save()
            return render(request, "progym/contato_resposta.html")
    else:
        form = MensagemForm()
    context = {
        "form": form,
    } 
    return render(request, "progym/contato.html", context)