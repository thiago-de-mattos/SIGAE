import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from unittest.mock import patch

from django.test import Client, SimpleTestCase

from atendimentos.services import estado


class FluxoWebTests(SimpleTestCase):
    def setUp(self):
        provedor = patch.object(estado, "_sistema", None)
        provedor.start()
        self.addCleanup(provedor.stop)
        self.operador = Client(enforce_csrf_checks=True)
        self.operador.get("/pacientes/")
        self.token = self.operador.cookies["csrftoken"].value

    def enviar(self, modulo, acao, **dados):
        return self.operador.post(
            f"/{modulo}/{acao}/", {**dados, "csrfmiddlewaretoken": self.token}
        )

    def paciente(self, nome, risco):
        return self.enviar("pacientes", "cadastrar", **{
            "cadastro-nome": nome,
            "cadastro-chegada": "2024-10-01T10:00",
            "cadastro-prioridade": risco,
        })

    def medico(self, nome):
        return self.enviar("medicos", "cadastrar", **{
            "cadastro-nome": nome,
            "cadastro-registro": f"FICT-{nome}",
        })

    def test_fluxo_compartilhado_com_tres_medicos_e_historico(self):
        for nome in ("Alfa", "Beta", "Gama"):
            self.assertRedirects(self.medico(nome), "/medicos/")

        for nome, risco in (("Ana", 5), ("Bia", 2), ("Cris", 2), ("Dani", 3)):
            self.assertRedirects(self.paciente(nome, risco), "/pacientes/")

        self.assertRedirects(self.enviar("triagem", "reclassificar", **{
            "reclassificacao-id": 4, "reclassificacao-prioridade": 1,
        }), "/triagem/")
        outro_operador = Client()
        triagem = outro_operador.get("/triagem/")
        self.assertEqual(triagem.context["proximo_paciente"]["nome"], "Dani")
        self.assertContains(outro_operador.get("/medicos/?id=2"), "FICT-Beta")

        for paciente, medico in (("Dani", "Alfa"), ("Bia", "Beta"), ("Cris", "Gama")):
            self.assertRedirects(self.enviar("triagem", "chamar"), "/atendimentos/")
            ativos = outro_operador.get("/atendimentos/").context["ativos"]
            self.assertEqual((ativos[-1]["paciente"]["nome"], ativos[-1]["medico"]["nome"]),
                             (paciente, medico))

        self.assertContains(self.enviar("triagem", "chamar"), "médico disponível", status_code=400)
        self.assertEqual([p["nome"] for p in outro_operador.get("/triagem/").context["fila"]], ["Ana"])

        self.assertRedirects(self.enviar("atendimentos", "concluir", id=1), "/atendimentos/")
        self.assertEqual(self.enviar("atendimentos", "concluir", id=1).status_code, 400)
        self.assertRedirects(self.enviar("atendimentos", "cancelar", id=2), "/atendimentos/")
        self.assertEqual(outro_operador.get("/triagem/").context["proximo_medico"]["nome"], "Beta")
        self.assertRedirects(self.enviar("triagem", "chamar"), "/atendimentos/")
        contexto = outro_operador.get("/historico/").context
        self.assertEqual([a["situacao"] for a in contexto["historico"]], ["Concluído", "Cancelado"])
        self.assertEqual([m["total"] for m in contexto["medicos"]], [1, 0, 0])
        estado.obter_sistema().validar_indices()

    def test_formulario_invalido_e_cancelamentos_usam_csrf_e_ids_corretos(self):
        falha = self.paciente(" ", 6)
        self.assertEqual(falha.status_code, 400)
        self.assertEqual(set(falha.context["cadastro"].errors), {"nome", "prioridade"})
        self.assertContains(self.operador.get("/pacientes/?id=1"), "Registro não encontrado.")

        self.assertRedirects(self.paciente("Paciente em espera", 5), "/pacientes/")
        self.assertEqual(self.operador.post("/pacientes/cancelar/", {"id": 1}).status_code, 403)
        self.assertEqual(self.operador.get("/pacientes/cancelar/").status_code, 405)
        self.assertEqual(self.enviar("atendimentos", "cancelar", id=1).status_code, 400)
        pagina = self.operador.get("/pacientes/").content.decode()
        formulario = pagina.split('action="/pacientes/cancelar/"', 1)[1].split("</form>", 1)[0]
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', formulario)
        self.assertIsNotNone(token)
        resposta = self.operador.post("/pacientes/cancelar/", {
            "id": 1, "csrfmiddlewaretoken": token.group(1),
        })
        self.assertRedirects(resposta, "/pacientes/")
        self.assertContains(self.operador.get("/pacientes/?id=1"), "Cancelado")
        self.assertEqual(self.operador.get("/historico/").context["historico"], [])

    def test_chamadas_web_concorrentes_criam_um_atendimento(self):
        self.assertRedirects(self.paciente("Ana", 3), "/pacientes/")
        self.assertRedirects(self.medico("Alfa"), "/medicos/")
        barreira = Barrier(2)

        def chamar():
            cliente = Client()
            barreira.wait(timeout=5)
            return cliente.post("/triagem/chamar/").status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(lambda _: chamar(), range(2)))
        self.assertCountEqual(resultados, [302, 400])
        sistema = estado.obter_sistema()
        self.assertEqual(len(sistema.listar_atendimentos_ativos()), 1)
        sistema.validar_indices()

    def test_cancelamento_na_triagem_atualiza_fila_indices_e_proxima_chamada(self):
        self.paciente("Ana", 1)
        self.paciente("Bia", 2)
        self.medico("Alfa")
        pagina = self.operador.get('/triagem/')
        self.assertContains(pagina, '<th scope="col">Ações</th>', html=True)
        html = pagina.content.decode()
        formulario = html.split('action="/pacientes/cancelar/"', 1)[1].split('</form>', 1)[0]
        self.assertIn('data-confirmar=', formulario)
        self.assertIn('class="secundario"', formulario)
        self.assertIn('name="retorno" value="triagem"', formulario)
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', formulario).group(1)
        response = self.operador.post('/pacientes/cancelar/', {
            'id': 1, 'retorno': 'triagem', 'csrfmiddlewaretoken': token,
        }, follow=True)
        self.assertRedirects(response, '/triagem/')
        self.assertContains(response, 'Paciente cancelado.')
        self.assertEqual([p['id'] for p in response.context['fila']], [2])
        self.assertEqual(response.context['proximo_paciente']['id'], 2)
        self.assertEqual(response.context['proximo_medico']['id'], 1)
        sistema = estado.obter_sistema()
        self.assertEqual(sistema.buscar_paciente(1).situacao, 'cancelado')
        self.assertEqual(sistema.listar_historico(), [])
        sistema.validar_indices()
        self.assertRedirects(self.enviar('pacientes', 'cancelar', id=2, retorno='triagem'), '/triagem/')
        vazia = self.operador.get('/triagem/')
        self.assertIsNone(vazia.context['proximo_paciente'])
        self.assertContains(vazia, '<button disabled>Chamar próximo</button>', html=True)
        sistema.validar_indices()

    def test_cancelamento_na_triagem_preserva_validacoes_e_contexto_em_erros(self):
        self.paciente('Ana', 1)
        self.assertEqual(self.operador.post('/pacientes/cancelar/', {
            'id': 1, 'retorno': 'triagem',
        }).status_code, 403)
        self.assertEqual(self.operador.get('/pacientes/cancelar/?retorno=triagem').status_code, 405)
        for id, mensagem in ((0, 'Informe um ID válido.'), (999, 'Registro não encontrado.')):
            response = self.enviar('pacientes', 'cancelar', id=id, retorno='triagem')
            self.assertContains(response, mensagem, status_code=400)
            self.assertTemplateUsed(response, 'atendimentos/triagem.html')
            self.assertEqual(response.context['proximo_paciente']['id'], 1)
        self.enviar('pacientes', 'cancelar', id=1, retorno='triagem')
        repetida = self.enviar('pacientes', 'cancelar', id=1, retorno='triagem')
        self.assertEqual(repetida.status_code, 400)
        self.assertTemplateUsed(repetida, 'atendimentos/triagem.html')
        self.assertEqual(repetida.context['fila'], [])
        estado.obter_sistema().validar_indices()

    def test_destino_de_cancelamento_aceita_somente_triagem_como_alternativa(self):
        self.paciente('Ana', 1)
        response = self.enviar('pacientes', 'cancelar', id=1, retorno='https://example.com/')
        self.assertRedirects(response, '/pacientes/')

    def test_inicio_anterior_a_chegada_preserva_fila_e_medico(self):
        sistema = estado.obter_sistema()
        chegada = datetime(2024, 10, 1, tzinfo=timezone.utc)
        paciente = sistema.cadastrar_paciente("Ana", chegada, 1)
        medico = sistema.cadastrar_medico("Alfa", "FICT-A")
        with self.assertRaisesRegex(ValueError, "anteceder a chegada"):
            sistema.chamar_proximo(chegada - timedelta(seconds=1))
        self.assertEqual(sistema.listar_fila(), [paciente])
        self.assertIs(sistema.consultar_proximo_medico(), medico)
        sistema.validar_indices()

    def test_chegada_fora_do_intervalo_de_brasilia_nao_compromete_as_paginas(self):
        resposta = self.enviar("pacientes", "cadastrar", **{
            "cadastro-nome": "Ana",
            "cadastro-chegada": "0001-01-01T00:00+00:00",
            "cadastro-prioridade": 1,
        })
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("chegada", resposta.context["cadastro"].errors)
        self.assertEqual(estado.obter_sistema().listar_pacientes(), [])
        self.assertEqual(self.operador.get("/pacientes/").status_code, 200)
        self.assertRedirects(self.paciente("Ana", 1), "/pacientes/")
