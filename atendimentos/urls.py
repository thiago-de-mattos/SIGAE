from django.urls import path

from . import views

app_name = "atendimentos"

urlpatterns = [
    path("", views.pagina, {"modulo": "inicio"}, name="inicio"),
    path("pacientes/", views.pagina, {"modulo": "pacientes"}, name="pacientes"),
    path("triagem/", views.pagina, {"modulo": "triagem"}, name="triagem"),
    path("medicos/", views.pagina, {"modulo": "medicos"}, name="medicos"),
    path("atendimentos/", views.pagina, {"modulo": "atendimentos"}, name="atendimentos"),
    path("historico/", views.pagina, {"modulo": "historico"}, name="historico"),
    path("<str:modulo>/<str:comando>/", views.acao, name="acao"),
]
