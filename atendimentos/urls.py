from django.urls import path

from . import views

app_name = "atendimentos"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("pacientes/", views.pacientes, name="pacientes"),
    path("triagem/", views.triagem, name="triagem"),
    path("medicos/", views.medicos, name="medicos"),
    path("atendimentos/", views.atendimentos, name="atendimentos"),
    path("historico/", views.historico, name="historico"),
]
