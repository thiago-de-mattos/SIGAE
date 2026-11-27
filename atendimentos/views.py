from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def inicio(request):
    return render(request, "atendimentos/inicio.html")


@require_GET
def pacientes(request):
    return render(request, "atendimentos/pacientes.html")


@require_GET
def triagem(request):
    return render(request, "atendimentos/triagem.html")


@require_GET
def medicos(request):
    return render(request, "atendimentos/medicos.html")


@require_GET
def atendimentos(request):
    return render(request, "atendimentos/atendimentos.html")


@require_GET
def historico(request):
    return render(request, "atendimentos/historico.html")
