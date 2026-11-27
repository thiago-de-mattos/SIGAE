from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch
from zoneinfo import ZoneInfo

from atendimentos.services.sistema_atendimento import SistemaAtendimento


INICIO = datetime(2026, 1, 1, tzinfo=timezone.utc)


class IndicadoresTests(TestCase):
    def preparar(self):
        s = SistemaAtendimento()
        for i in range(3):
            s.cadastrar_medico(f'Médico {i}', f'FICTICIO-{i}')
        for i in range(6):
            s.cadastrar_paciente(f'Paciente {i}', INICIO, 3)
        return s

    def misto(self):
        s = self.preparar()
        a, b, c = [s.chamar_proximo(INICIO) for _ in range(3)]
        s.concluir_atendimento(a.id, INICIO)
        s.cancelar_paciente(b.paciente.id, INICIO)
        s.cancelar_paciente(4, INICIO)
        return s, a, b, c

    def test_vazio_inclui_todos_estados_zerados(self):
        s = SistemaAtendimento()
        self.assertEqual(s.obter_indicadores(), {
            'total_pacientes': 0,
            'pacientes_por_estado': {'aguardando': 0, 'em_atendimento': 0, 'concluido': 0, 'cancelado': 0},
            'total_medicos': 0,
            'medicos_por_estado': {'disponivel': 0, 'em_atendimento': 0},
            'conclusoes_por_medico': [],
            'total_atendimentos': 0,
            'atendimentos_por_estado': {'em_atendimento': 0, 'concluido': 0, 'cancelado': 0},
        })
        for consulta in (s.listar_fila, s.listar_chegadas, s.listar_historico, s.listar_atendimentos_ativos):
            self.assertEqual(consulta(), [])
        self.assertIsNone(s.consultar_proximo_paciente())
        self.assertIsNone(s.consultar_proximo_medico())

    def test_estados_mistos_e_cancelamento_na_espera_distinto(self):
        s, a, b, c = self.misto()
        dados = s.obter_indicadores()
        self.assertEqual(dados['total_pacientes'], 6)
        self.assertEqual(dados['pacientes_por_estado'], {'aguardando': 2, 'em_atendimento': 1, 'concluido': 1, 'cancelado': 2})
        self.assertEqual(dados['total_medicos'], 3)
        self.assertEqual(dados['medicos_por_estado'], {'disponivel': 2, 'em_atendimento': 1})
        self.assertEqual(dados['total_atendimentos'], 3)
        self.assertEqual(dados['atendimentos_por_estado'], {'em_atendimento': 1, 'concluido': 1, 'cancelado': 1})
        self.assertEqual(s.listar_historico(), [a, b])
        self.assertEqual(s.listar_atendimentos_ativos(), [c])
        for linha in dados['conclusoes_por_medico']:
            self.assertIs(s.buscar_medico(linha['medico'].id), linha['medico'])
            self.assertEqual(linha['total_concluidos'], int(linha['medico'] is a.medico))
        self.assertIs(s.consultar_proximo_medico(), b.medico)

    def test_historico_expoe_campos_e_ordena_inicio_depois_id(self):
        s = self.preparar()
        a = s.chamar_proximo(INICIO + timedelta(hours=2))
        b = s.chamar_proximo(INICIO)
        c = s.chamar_proximo(INICIO)
        for atendimento in (c, a, b):
            s.concluir_atendimento(atendimento.id, INICIO + timedelta(hours=3))
        historico = s.listar_historico()
        self.assertEqual(historico, [b, c, a])
        for item in historico:
            self.assertIs(s._atendimentos.buscar(item.id), item)
            self.assertIs(s.buscar_paciente(item.paciente.id), item.paciente)
            self.assertIs(s.buscar_medico(item.medico.id), item.medico)
            self.assertEqual(item.situacao, 'concluido')
            self.assertEqual(item.fim, INICIO + timedelta(hours=3))
            self.assertLessEqual(item.inicio, item.fim)

    def test_chegadas_incluem_todos_estados_e_desempate_por_id(self):
        s = SistemaAtendimento()
        s.cadastrar_medico('Médica', 'FICTICIO')
        tarde = s.cadastrar_paciente('Tarde', INICIO + timedelta(hours=1), 1)
        primeiro = s.cadastrar_paciente('Primeiro', INICIO, 2)
        segundo = s.cadastrar_paciente('Segundo', INICIO, 3)
        espera = s.cadastrar_paciente('Espera', INICIO, 4)
        a = s.chamar_proximo(INICIO + timedelta(hours=2))
        s.concluir_atendimento(a.id, a.inicio)
        s.cancelar_paciente(segundo.id, a.inicio)
        s.chamar_proximo(a.inicio)
        self.assertEqual(s.listar_chegadas(), [primeiro, segundo, espera, tarde])
        self.assertEqual(s.listar_fila(), [espera])

    def test_minimos_clinico_e_medico_sem_extracao(self):
        s = self.preparar()
        s.reclassificar_paciente(6, 1)
        self.assertIs(s.consultar_proximo_paciente(), s.buscar_paciente(6))
        self.assertIs(s.consultar_proximo_medico(), s.buscar_medico(1))
        a = s.chamar_proximo(INICIO)
        s.concluir_atendimento(a.id, INICIO)
        self.assertIs(s.consultar_proximo_paciente(), s.buscar_paciente(1))
        self.assertIs(s.consultar_proximo_medico(), s.buscar_medico(2))
        for _ in range(2):
            s.chamar_proximo(INICIO)
        self.assertIs(s.consultar_proximo_medico(), s.buscar_medico(1))

    def test_consultas_nao_mutam_entidades_indices_ou_ids(self):
        s, _, _, _ = self.misto()
        entidades = s.listar_pacientes() + s.listar_medicos() + s._atendimentos.listar_valores()
        antes = [vars(e).copy() for e in entidades]
        heaps = [list(s._heap_pacientes._itens), list(s._heap_medicos._itens)]
        raiz = s._arvore_espera._raiz
        ids = (s._ultimo_id_paciente, s._ultimo_id_medico, s._ultimo_id_atendimento)
        with ExitStack() as pilha:
            for indice in (s._pacientes, s._medicos, s._atendimentos, s._arvore_espera, s._heap_pacientes, s._heap_medicos):
                for nome in ('inserir', 'remover', 'atualizar', 'extrair_minimo'):
                    if hasattr(indice, nome):
                        pilha.enter_context(patch.object(indice, nome, side_effect=AssertionError('mutação indevida')))
            percurso = pilha.enter_context(patch.object(s._arvore_espera, 'em_ordem', wraps=s._arvore_espera.em_ordem))
            for _ in range(3):
                s.obter_indicadores()
                s.listar_historico()
                s.listar_atendimentos_ativos()
                s.listar_chegadas()
                s.listar_fila()
                s.consultar_proximo_paciente()
                s.consultar_proximo_medico()
            self.assertEqual(percurso.call_count, 3)
        self.assertEqual([vars(e) for e in entidades], antes)
        self.assertEqual([s._heap_pacientes._itens, s._heap_medicos._itens], heaps)
        self.assertIs(s._arvore_espera._raiz, raiz)
        self.assertEqual((s._ultimo_id_paciente, s._ultimo_id_medico, s._ultimo_id_atendimento), ids)
        for indice in (s._pacientes, s._medicos, s._atendimentos, s._arvore_espera, s._heap_pacientes, s._heap_medicos):
            indice.validar()

    def test_resultados_auxiliares_independentes(self):
        s, a, b, c = self.misto()
        dados = s.obter_indicadores()
        dados['pacientes_por_estado']['aguardando'] = 999
        dados['conclusoes_por_medico'][0]['total_concluidos'] = 999
        dados['conclusoes_por_medico'].clear()
        for consulta in (s.listar_historico, s.listar_chegadas, s.listar_fila, s.listar_atendimentos_ativos):
            consulta().clear()
        self.assertEqual(s.obter_indicadores()['pacientes_por_estado']['aguardando'], 2)
        self.assertEqual(len(s.obter_indicadores()['conclusoes_por_medico']), 3)
        self.assertEqual(s.listar_historico(), [a, b])
        self.assertEqual(s.listar_atendimentos_ativos(), [c])
        self.assertEqual(len(s.listar_chegadas()), 6)
        self.assertEqual(len(s.listar_fila()), 2)

    def test_totais_reais_apos_ciclos_completos_e_ids_reservados(self):
        s = self.preparar()
        with self.assertRaises(ValueError):
            s.cadastrar_paciente('', INICIO, 1)
        for i in range(30):
            p = s.cadastrar_paciente(f'Extra {i}', INICIO, 3)
            if i % 3 == 0:
                s.cancelar_paciente(p.id, INICIO)
                s.cadastrar_paciente(f'Reposição {i}', INICIO, 3)
            a = s.chamar_proximo(INICIO)
            if i % 2:
                s.concluir_atendimento(a.id, INICIO)
            else:
                s.cancelar_paciente(a.paciente.id, INICIO)
            dados = s.obter_indicadores()
            pacientes, medicos = s.listar_pacientes(), s.listar_medicos()
            atendimentos = s._atendimentos.listar_valores()
            self.assertEqual(dados['total_pacientes'], len(pacientes))
            self.assertEqual(dados['total_medicos'], len(medicos))
            self.assertEqual(dados['total_atendimentos'], len(atendimentos))
            for chave, registros in (('pacientes_por_estado', pacientes), ('medicos_por_estado', medicos), ('atendimentos_por_estado', atendimentos)):
                for estado, quantidade in dados[chave].items():
                    self.assertEqual(quantidade, sum(r.situacao == estado for r in registros))
                self.assertEqual(sum(dados[chave].values()), len(registros))
            for linha in dados['conclusoes_por_medico']:
                self.assertEqual(linha['total_concluidos'], sum(a.medico is linha['medico'] and a.situacao == 'concluido' for a in atendimentos))
        self.assertEqual(s.listar_atendimentos_ativos(), [])
        self.assertEqual(len(s.listar_historico()), 30)

    def test_historico_ordena_instantes_distintos_na_hora_repetida(self):
        fuso = ZoneInfo("America/New_York")
        cedo = datetime(2026, 11, 1, 1, 30, tzinfo=fuso)
        tarde = cedo.replace(fold=1)
        sistema = self.preparar()
        primeiro = sistema.chamar_proximo(tarde)
        segundo = sistema.chamar_proximo(cedo)
        sistema.concluir_atendimento(primeiro.id, tarde)
        sistema.concluir_atendimento(segundo.id, cedo)
        self.assertEqual(sistema.listar_historico(), [segundo, primeiro])
