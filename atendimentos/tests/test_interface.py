from html.parser import HTMLParser
from unittest.mock import patch

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase
from django.utils import timezone

from atendimentos.services import estado


class Elementos(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elementos = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elementos.append((tag, dict(attrs)))


class InterfaceTests(SimpleTestCase):
    def setUp(self):
        provedor = patch.object(estado, '_sistema', None)
        provedor.start()
        self.addCleanup(provedor.stop)

    def test_cadastro_novo_permite_inicializar_chegada_editavel(self):
        response = self.client.get('/pacientes/')
        elementos = Elementos(response.content.decode()).elementos
        self.assertTrue(any(tag == 'form' and 'data-chegada-atual' in attrs
                            for tag, attrs in elementos))
        campo = next(attrs for tag, attrs in elementos
                     if tag == 'input' and attrs.get('name') == 'cadastro-chegada')
        self.assertEqual(campo['type'], 'datetime-local')
        self.assertNotIn('readonly', campo)
        self.assertNotIn('disabled', campo)

    def test_seletores_de_risco_obrigatorios_sem_preselecao(self):
        for url, nome in (('/pacientes/', 'cadastro-prioridade'),
                          ('/triagem/', 'reclassificacao-prioridade')):
            with self.subTest(url=url):
                elementos = Elementos(self.client.get(url).content.decode()).elementos
                campos = [attrs for tag, attrs in elementos
                          if tag == 'input' and attrs.get('name') == nome]
                self.assertEqual([c['value'] for c in campos], ['1', '2', '3', '4', '5'])
                for campo in campos:
                    self.assertEqual(campo['type'], 'radio')
                    self.assertIn('required', campo)
                    self.assertNotIn('checked', campo)
                    self.assertTrue(any(tag == 'label' and attrs.get('for') == campo['id']
                                        for tag, attrs in elementos))
                self.assertFalse(any(tag == 'select' and attrs.get('name') == nome
                                     for tag, attrs in elementos))

    def test_seletores_preservam_valor_e_associam_erro_apos_post(self):
        for url, prefixo in (('/pacientes/cadastrar/', 'cadastro'),
                             ('/triagem/reclassificar/', 'reclassificacao')):
            for valor in ('1', '2', '3', '4', '5', '', '6'):
                with self.subTest(url=url, valor=valor):
                    # Demais campos ausentes provocam erro sem alterar o estado.
                    response = self.client.post(url, {f'{prefixo}-prioridade': valor})
                    self.assertEqual(response.status_code, 400)
                    elementos = Elementos(response.content.decode()).elementos
                    campos = [attrs for tag, attrs in elementos if tag == 'input'
                              and attrs.get('name') == f'{prefixo}-prioridade']
                    self.assertEqual(len(campos), 5)
                    self.assertEqual([c['value'] for c in campos if 'checked' in c],
                                     [valor] if valor in ('1', '2', '3', '4', '5') else [])
                    if valor in ('', '6'):
                        for campo in campos:
                            self.assertEqual(campo['aria-invalid'], 'true')
                            self.assertTrue(any(attrs.get('id') == campo['aria-describedby']
                                                for _, attrs in elementos))

    def test_erro_de_cadastro_preserva_chegada_inclusive_vazia(self):
        for chegada in ('2024-10-01T10:30', ''):
            with self.subTest(chegada=chegada):
                response = self.client.post('/pacientes/cadastrar/', {
                    'cadastro-nome': '', 'cadastro-chegada': chegada,
                    'cadastro-prioridade': '1',
                })
                self.assertEqual(response.status_code, 400)
                elementos = Elementos(response.content.decode()).elementos
                self.assertFalse(any('data-chegada-atual' in attrs for _, attrs in elementos))
                campo = next(attrs for tag, attrs in elementos
                             if tag == 'input' and attrs.get('name') == 'cadastro-chegada')
                self.assertEqual(campo.get('value', ''), chegada)

    def test_confirmacao_preserva_nome_escapado_e_contrato_do_formulario(self):
        nome = 'Paciente "Teste" <script>alert(1)</script>'
        paciente = estado.obter_sistema().cadastrar_paciente(nome, timezone.now(), 1)
        response = self.client.get('/pacientes/')
        html = response.content.decode()
        elementos = Elementos(html).elementos
        formulario = next(attrs for tag, attrs in elementos
                          if tag == 'form' and attrs.get('action') == '/pacientes/cancelar/')
        self.assertEqual(formulario['method'], 'post')
        self.assertIn(nome, formulario['data-confirmar'])
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertTrue(any(tag == 'input' and attrs.get('name') == 'csrfmiddlewaretoken'
                            for tag, attrs in elementos))
        self.assertTrue(any(tag == 'input' and attrs.get('name') == 'id'
                            and attrs.get('value') == str(paciente.id) for tag, attrs in elementos))

    def test_riscos_e_situacoes_tem_texto_alem_da_cor(self):
        sistema = estado.obter_sistema()
        for risco in range(1, 6):
            sistema.cadastrar_paciente(f'Paciente {risco}', timezone.now(), risco)
        response = self.client.get('/pacientes/')
        for risco, texto in ((1, 'Emergência'), (2, 'Muito urgente'), (3, 'Urgente'),
                             (4, 'Pouco urgente'), (5, 'Não urgente')):
            self.assertContains(response, f'<span class="risco r{risco}">{risco} {texto}</span>', html=True)
        self.assertContains(response, '<span class="situacao aguardando">Aguardando</span>', count=5, html=True)

    def test_recursos_estaticos_e_foco_de_erros_disponiveis(self):
        for recurso in ('css/base.css', 'atendimentos/interface.js'):
            self.assertIsNotNone(finders.find(recurso))
        response = self.client.get('/pacientes/?id=0')
        elementos = Elementos(response.content.decode()).elementos
        campo = next(attrs for tag, attrs in elementos
                     if tag == 'input' and attrs.get('name') == 'id')
        self.assertEqual(campo['aria-invalid'], 'true')
        self.assertIn('id_id_error', campo['aria-describedby'])
