from django.test import SimpleTestCase
from django.urls import reverse


class InicioTests(SimpleTestCase):
    def test_inicio_renderiza_template_com_css_e_aviso_academico(self):
        response = self.client.get(reverse("atendimentos:inicio"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "atendimentos/inicio.html")
        self.assertContains(response, "SIGAE WEB")
        self.assertContains(response, "/static/css/base.css")
        self.assertContains(response, "simulador acadêmico")

    def test_inicio_nao_aceita_post(self):
        response = self.client.post(reverse("atendimentos:inicio"))

        self.assertEqual(response.status_code, 405)


class ModulosTests(SimpleTestCase):
    modulos = ("inicio", "pacientes", "triagem", "medicos", "atendimentos", "historico")

    def test_telas_navegaveis_com_pagina_atual(self):
        for modulo in self.modulos:
            with self.subTest(modulo=modulo):
                response = self.client.get(reverse(f"atendimentos:{modulo}"))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, f"atendimentos/{modulo}.html")
                self.assertContains(response, 'aria-current="page"', count=1)
                for destino in self.modulos:
                    self.assertContains(response, f'href="{reverse(f"atendimentos:{destino}")}"')

    def test_todas_as_views_rejeitam_metodos_diferentes_de_get(self):
        for modulo in self.modulos:
            for metodo in ("POST", "PUT", "PATCH", "DELETE", "HEAD"):
                with self.subTest(modulo=modulo, metodo=metodo):
                    response = self.client.generic(metodo, reverse(f"atendimentos:{modulo}"))
                    self.assertEqual(response.status_code, 405)

    def test_triagem_apresenta_cinco_classificacoes_e_chamada_indisponivel_na_fila_vazia(self):
        response = self.client.get(reverse("atendimentos:triagem"))
        for risco in ("1 Emergência", "2 Muito urgente", "3 Urgente", "4 Pouco urgente", "5 Não urgente"):
            self.assertContains(response, risco)
        self.assertContains(response, '<button disabled>Chamar próximo</button>', html=True)
        self.assertContains(response, '<button>Reclassificar</button>', html=True)
