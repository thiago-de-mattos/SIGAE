from datetime import datetime, timedelta, timezone
from unittest import TestCase

from atendimentos.domain.atendimento import Atendimento
from atendimentos.domain.medico import Medico
from atendimentos.domain.paciente import Paciente
from atendimentos.services.sistema_atendimento import SistemaAtendimento
from atendimentos.structures.arvore_rubro_negra import ArvoreRubroNegra
from atendimentos.structures.min_heap import MinHeap
from atendimentos.structures.tabela_hash import TabelaHash


INICIO = datetime(2026, 11, 26, 10, tzinfo=timezone.utc)


class SistemaAtendimentoTests(TestCase):
    def estruturas(self, sistema):
        return (sistema._pacientes, sistema._medicos, sistema._atendimentos,
                sistema._arvore_espera, sistema._heap_pacientes, sistema._heap_medicos)

    def test_inicializa_estruturas_proprias_vazias_e_validas(self):
        sistema = SistemaAtendimento()
        tipos = (TabelaHash, TabelaHash, TabelaHash, ArvoreRubroNegra, MinHeap, MinHeap)
        for estrutura, tipo in zip(self.estruturas(sistema), tipos):
            self.assertIsInstance(estrutura, tipo)
            self.assertEqual(len(estrutura), 0)
            self.assertIsNone(estrutura.validar())
        self.assertIsNone(sistema._heap_pacientes.consultar_minimo())
        self.assertIsNone(sistema._heap_medicos.consultar_minimo())
        self.assertEqual(sistema._arvore_espera.em_ordem(), [])

    def test_ids_sequenciais_independentes_por_tipo(self):
        sistema = SistemaAtendimento()
        self.assertEqual([sistema._reservar_id_paciente() for _ in range(100)], list(range(1, 101)))
        self.assertEqual(sistema._reservar_id_medico(), 1)
        self.assertEqual(sistema._reservar_id_atendimento(), 1)
        self.assertEqual(sistema._reservar_id_paciente(), 101)
        self.assertEqual(sistema._reservar_id_atendimento(), 2)
        self.assertEqual(sistema._reservar_id_medico(), 2)
        for estrutura in self.estruturas(sistema):
            self.assertEqual(len(estrutura), 0)

    def test_reservas_descartadas_nao_sao_reutilizadas(self):
        sistema = SistemaAtendimento()
        for reservar in (sistema._reservar_id_paciente, sistema._reservar_id_medico,
                         sistema._reservar_id_atendimento):
            self.assertEqual(reservar(), 1)
            self.assertEqual(reservar(), 2)
            self.assertEqual(reservar(), 3)
        # Uma construção inválida após a reserva também consome o ID.
        with self.assertRaises(ValueError):
            Paciente(sistema._reservar_id_paciente(), "", INICIO, 3)
        self.assertEqual(sistema._reservar_id_paciente(), 5)

    def test_remocoes_nao_reiniciam_geradores(self):
        sistema = SistemaAtendimento()
        paciente = Paciente(sistema._reservar_id_paciente(), "Ana", INICIO, 3)
        medico = Medico(sistema._reservar_id_medico(), "Lia", "FICT-001")
        atendimento = Atendimento(sistema._reservar_id_atendimento(), paciente, medico, INICIO)
        for tabela, item in ((sistema._pacientes, paciente), (sistema._medicos, medico),
                             (sistema._atendimentos, atendimento)):
            tabela.inserir(item.id, item)
            self.assertIs(tabela.remover(item.id), item)
            self.assertEqual(len(tabela), 0)
        self.assertEqual(sistema._reservar_id_paciente(), 2)
        self.assertEqual(sistema._reservar_id_medico(), 2)
        self.assertEqual(sistema._reservar_id_atendimento(), 2)

    def test_instancias_nao_compartilham_estruturas_ou_contadores(self):
        primeiro, segundo = SistemaAtendimento(), SistemaAtendimento()
        for a, b in zip(self.estruturas(primeiro), self.estruturas(segundo)):
            self.assertIsNot(a, b)
        paciente = Paciente(primeiro._reservar_id_paciente(), "Ana", INICIO, 3)
        medico = Medico(primeiro._reservar_id_medico(), "Lia", "FICT-001")
        atendimento = Atendimento(primeiro._reservar_id_atendimento(), paciente, medico, INICIO)
        primeiro._pacientes.inserir(paciente.id, paciente)
        primeiro._medicos.inserir(medico.id, medico)
        primeiro._atendimentos.inserir(atendimento.id, atendimento)
        primeiro._arvore_espera.inserir(paciente.chave_chegada, paciente)
        primeiro._heap_pacientes.inserir(paciente)
        primeiro._heap_medicos.inserir(medico)
        for estrutura in self.estruturas(segundo):
            self.assertEqual(len(estrutura), 0)
            estrutura.validar()
        for nome in ("_reservar_id_paciente", "_reservar_id_medico", "_reservar_id_atendimento"):
            self.assertEqual(getattr(segundo, nome)(), 1)
            self.assertEqual(getattr(primeiro, nome)(), 2)

    def test_pacientes_ordenados_por_risco_chegada_e_id(self):
        sistema = SistemaAtendimento()
        pacientes = [Paciente(4, "D", INICIO, 5),
                     Paciente(3, "C", INICIO + timedelta(minutes=1), 1),
                     Paciente(2, "B", INICIO, 1), Paciente(1, "A", INICIO, 1)]
        for paciente in pacientes:
            sistema._heap_pacientes.inserir(paciente)
            sistema._arvore_espera.inserir(paciente.chave_chegada, paciente)
            sistema._pacientes.inserir(paciente.id, paciente)
        self.assertEqual([p.id for p in sistema._arvore_espera.em_ordem()], [1, 2, 4, 3])
        for esperado in reversed(pacientes):
            self.assertIs(sistema._heap_pacientes.extrair_minimo(), esperado)
            self.assertIs(sistema._pacientes.buscar(esperado.id), esperado)
        self.assertEqual(len(sistema._heap_medicos), 0)

    def test_medicos_ordenados_por_carga_atribuicao_e_id(self):
        sistema = SistemaAtendimento()
        medicos = [Medico(id, f"Médico {id}", f"FICT-{id}") for id in range(1, 7)]
        for indice, inicio in ((0, INICIO), (1, INICIO + timedelta(hours=1)),
                              (2, INICIO), (3, INICIO)):
            medicos[indice].iniciar_atendimento(inicio)
            if indice == 0:
                medicos[indice].concluir_atendimento()
            else:
                medicos[indice].cancelar_atendimento()
        for medico in medicos:
            sistema._heap_medicos.inserir(medico)
        for id in (5, 6, 3, 4, 2, 1):
            self.assertIs(sistema._heap_medicos.extrair_minimo(), medicos[id - 1])
            sistema._heap_medicos.validar()
        self.assertEqual(len(sistema._heap_pacientes), 0)
        self.assertIsNot(sistema._heap_pacientes._posicoes, sistema._heap_medicos._posicoes)

    def test_armazenamento_atendimentos_preserva_referencia(self):
        sistema = SistemaAtendimento()
        paciente = Paciente(1, "Ana", INICIO, 3)
        medico = Medico(1, "Lia", "FICT-001")
        atendimento = Atendimento(sistema._reservar_id_atendimento(), paciente, medico, INICIO)
        sistema._atendimentos.inserir(atendimento.id, atendimento)
        atendimento.concluir(INICIO + timedelta(minutes=20))
        self.assertIs(sistema._atendimentos.buscar(atendimento.id), atendimento)
        self.assertIs(sistema._atendimentos.buscar(atendimento.id).paciente, paciente)
        self.assertIs(sistema._atendimentos.buscar(atendimento.id).medico, medico)
        sistema._atendimentos.validar()
