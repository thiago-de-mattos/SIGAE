"""Cenários integrados determinísticos; oráculos auxiliares não são índices do serviço."""
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from atendimentos.services.sistema_atendimento import SistemaAtendimento
from atendimentos.structures.tabela_hash import TabelaHash
from atendimentos.structures.min_heap import MinHeap
from atendimentos.structures.arvore_rubro_negra import ArvoreRubroNegra


T = datetime(2026, 1, 1, tzinfo=timezone.utc)


class IntegracaoServicoTests(TestCase):
    def setUp(self):
        self.s = SistemaAtendimento()

    def conferir(self):
        s = self.s
        ps, ms = s.listar_pacientes(), s.listar_medicos()
        ats = s._atendimentos.listar_valores()
        for h in (s._pacientes, s._medicos, s._atendimentos,
                  s._heap_pacientes._posicoes, s._heap_medicos._posicoes):
            self.assertIsInstance(h, TabelaHash)
            h.validar()
        self.assertIsInstance(s._arvore_espera, ArvoreRubroNegra)
        s._arvore_espera.validar()
        espera = [p for p in ps if p.situacao == 'aguardando']
        livres = [m for m in ms if m.situacao == 'disponivel']
        self.assertEqual(s.listar_fila(), sorted(espera, key=lambda p: p.chave_chegada))
        self.assertEqual(s.listar_chegadas(), sorted(ps, key=lambda p: p.chave_chegada))
        for heap, itens in ((s._heap_pacientes, espera), (s._heap_medicos, livres)):
            self.assertIsInstance(heap, MinHeap)
            heap.validar()
            self.assertEqual(len(heap), len(itens))
            for item in itens:
                pos = heap._posicoes.buscar(item.id)
                self.assertIsNotNone(pos)
                self.assertIs(heap._itens[pos], item)
            self.assertIs(heap.consultar_minimo(), min(itens, key=lambda r: r.chave_prioridade, default=None))
        for p in ps:
            self.assertIs(s.buscar_paciente(p.id), p)
            self.assertIs(s._arvore_espera.buscar(p.chave_chegada), p if p in espera else None)
            vinculados = [a for a in ats if a.paciente is p]
            self.assertLessEqual(len(vinculados), 1)
            self.assertEqual(sum(a.situacao == 'em_atendimento' for a in vinculados), int(p.situacao == 'em_atendimento'))
            for a in vinculados:
                self.assertEqual(a.situacao.value, p.situacao.value)
        for m in ms:
            self.assertIs(s.buscar_medico(m.id), m)
            self.assertEqual(sum(a.medico is m and a.situacao == 'em_atendimento' for a in ats), int(m.situacao == 'em_atendimento'))
            self.assertEqual(m.total_concluidos, sum(a.medico is m and a.situacao == 'concluido' for a in ats))
        for a in ats:
            self.assertIs(s.buscar_paciente(a.paciente.id), a.paciente)
            self.assertIs(s.buscar_medico(a.medico.id), a.medico)
            if a.situacao == 'em_atendimento':
                self.assertIsNone(a.fim)
            else:
                self.assertGreaterEqual(a.fim, a.inicio)
        self.assertEqual(s.listar_historico(), sorted([a for a in ats if a.situacao != 'em_atendimento'], key=lambda a: (a.inicio, a.id)))
        self.assertEqual(s.listar_atendimentos_ativos(), [a for a in ats if a.situacao == 'em_atendimento'])
        d = s.obter_indicadores()
        for campo, total, itens in (('pacientes_por_estado', 'total_pacientes', ps), ('medicos_por_estado', 'total_medicos', ms), ('atendimentos_por_estado', 'total_atendimentos', ats)):
            self.assertEqual(d[total], len(itens))
            for estado, n in d[campo].items():
                self.assertEqual(n, sum(i.situacao == estado for i in itens))
        for linha in d['conclusoes_por_medico']:
            self.assertEqual(linha['total_concluidos'], sum(a.medico is linha['medico'] and a.situacao == 'concluido' for a in ats))

    def operar(self, metodo, *args):
        resultado = metodo(*args)
        self.conferir()
        return resultado

    def chamar(self, instante=T):
        p = self.s.consultar_proximo_paciente()
        m = self.s.consultar_proximo_medico()
        a = self.operar(self.s.chamar_proximo, instante)
        self.assertIs(a.paciente, p)
        self.assertIs(a.medico, m)
        return a

    def test_fluxo_completo_com_desempates_e_indisponibilidade(self):
        s = self.s
        ms = [self.operar(s.cadastrar_medico, f'Médico fictício {i}', f'FICTICIO-{i}') for i in range(3)]
        ps = [self.operar(s.cadastrar_paciente, f'Paciente fictício {i}', T + timedelta(minutes=i % 3), 5) for i in range(12)]
        # Triagem no cadastro; reclassificação posterior sem novo cadastro.
        for p in ps:
            self.operar(s.reclassificar_paciente, p.id, 1 if p.id % 2 else 3)
        a, b, c = [self.chamar(T + timedelta(hours=1)) for _ in range(3)]
        self.assertEqual([a.medico, b.medico, c.medico], ms)
        self.assertEqual([a.paciente, b.paciente, c.paciente], [ps[0], ps[6], ps[4]])
        antes = (s.listar_fila(), s.obter_indicadores(), s._ultimo_id_atendimento)
        with self.assertRaises(ValueError):
            s.chamar_proximo(T)
        self.assertEqual(antes, (s.listar_fila(), s.obter_indicadores(), s._ultimo_id_atendimento))
        self.conferir()
        self.operar(s.concluir_atendimento, a.id, T + timedelta(hours=2))
        self.operar(s.cancelar_paciente, b.paciente.id, T + timedelta(hours=2))
        self.operar(s.cancelar_paciente, c.paciente.id, T + timedelta(hours=2))
        # Carga zero vence; atribuições iguais desempata por ID.
        d = self.chamar(T + timedelta(hours=3))
        self.assertIs(d.medico, ms[1])
        self.operar(s.cancelar_paciente, d.paciente.id, T + timedelta(hours=4))
        e = self.chamar(T + timedelta(hours=5))
        self.assertIs(e.medico, ms[2])  # Última atribuição mais antiga.
        self.operar(s.concluir_atendimento, e.id, T + timedelta(hours=6))
        self.operar(s.cancelar_paciente, s.listar_fila()[-1].id, T + timedelta(hours=6))
        while s.listar_fila():
            atual = self.chamar(T + timedelta(hours=7))
            self.operar(s.concluir_atendimento, atual.id, T + timedelta(hours=8))
        self.assertEqual(s.listar_atendimentos_ativos(), [])
        self.assertEqual(len(s.listar_historico()), 11)

    def test_colisoes_rehash_e_arvore_durante_ciclos(self):
        s = self.s
        # Reservas descartadas são reais: validação rejeita os cadastros e consome ID.
        for i in range(20):
            if i:
                for _ in range(87):
                    with self.assertRaises(ValueError):
                        s.cadastrar_paciente('', T, 1)
                    with self.assertRaises(ValueError):
                        s.cadastrar_medico('', 'FICTICIO')
            self.operar(s.cadastrar_paciente, f'Paciente {i}', T + timedelta(minutes=20-i), i % 5 + 1)
            self.operar(s.cadastrar_medico, f'Médico {i}', 'FICTICIO')
        hashes = (s._pacientes, s._medicos, s._heap_pacientes._posicoes, s._heap_medicos._posicoes)
        for h in hashes:
            self.assertGreaterEqual(h._capacidade, 44)
            self.assertTrue(any(len(bucket) > 1 for bucket in h._buckets))
        for i in range(20):
            a = self.chamar(T + timedelta(hours=1))
            if i % 2:
                self.operar(s.concluir_atendimento, a.id, T + timedelta(hours=2))
            else:
                self.operar(s.cancelar_paciente, a.paciente.id, T + timedelta(hours=2))
        self.assertGreaterEqual(s._atendimentos._capacidade, 44)
        self.assertEqual(len(s._arvore_espera), 0)
        self.assertEqual(sum(m.total_concluidos for m in s.listar_medicos()), 10)

    def test_recuperacao_em_fluxo_com_historico_e_continuidade(self):
        s = self.s
        self.operar(s.cadastrar_medico, 'Médica fictícia', 'FICTICIO')
        for i in range(12):
            self.operar(s.cadastrar_paciente, f'Paciente {i}', T, 3)
        a = self.chamar()
        self.operar(s.concluir_atendimento, a.id, T)
        # Falhas após mutações completas, numa sessão com histórico preservado.
        for etapa in ('reclassificar', 'chamar', 'concluir', 'cancelar_ativo', 'cancelar_espera'):
            if etapa in ('concluir', 'cancelar_ativo'):
                a = self.chamar()
            p = s.consultar_proximo_paciente()
            if etapa == 'reclassificar':
                objeto, nome, acao = s._heap_pacientes, 'atualizar', lambda: s.reclassificar_paciente(p.id, 1)
            elif etapa == 'chamar':
                objeto, nome, acao = s._atendimentos, 'inserir', lambda: s.chamar_proximo(T)
            elif etapa == 'concluir':
                objeto, nome, acao = s._heap_medicos, 'inserir', lambda: s.concluir_atendimento(a.id, T)
            elif etapa == 'cancelar_ativo':
                objeto, nome, acao = s._heap_medicos, 'inserir', lambda: s.cancelar_paciente(a.paciente.id, T)
            else:
                objeto, nome, acao = s._arvore_espera, 'remover', lambda: s.cancelar_paciente(p.id, T)
            original = getattr(objeto, nome)
            chamadas = []
            antes = s.obter_indicadores()

            def falhar_uma_vez(*args):
                resultado = original(*args)
                chamadas.append(args)
                if len(chamadas) == 1:
                    raise RuntimeError('falha recuperável integrada')
                return resultado

            with patch.object(objeto, nome, side_effect=falhar_uma_vez):
                with self.assertRaises(RuntimeError):
                    acao()
            self.conferir()
            self.assertEqual(s.obter_indicadores(), antes)
            if etapa in ('concluir', 'cancelar_ativo'):
                self.operar(s.concluir_atendimento, a.id, T)
        while s.consultar_proximo_paciente():
            a = self.chamar()
            self.operar(s.concluir_atendimento, a.id, T)
        self.assertEqual(len(s.listar_historico()), 12)
        self.assertEqual(s.buscar_medico(1).total_concluidos, 12)
