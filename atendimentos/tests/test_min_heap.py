from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from random import Random
from unittest import TestCase

from atendimentos.domain.paciente import Paciente
from atendimentos.structures.min_heap import MinHeap


@dataclass
class MedicoFicticio:
    id: int
    total_concluidos: int = 0
    ultima_atribuicao: datetime | None = None


MINIMO = datetime.min.replace(tzinfo=timezone.utc)
AGORA = datetime(2026, 11, 26, tzinfo=timezone.utc)


def chave_medico(medico):
    return (medico.total_concluidos, medico.ultima_atribuicao or MINIMO, medico.id)


class MinHeapTests(TestCase):
    def paciente(self, id, prioridade=3, minutos=0):
        return Paciente(id, f"Paciente {id}", AGORA + timedelta(minutes=minutos), prioridade)

    def conferir(self, heap):
        self.assertIsNone(heap.validar())
        self.assertEqual(len(heap), len(heap._posicoes))
        for posicao, item in enumerate(heap._itens):
            self.assertEqual(heap._posicoes.buscar(item.id), posicao)

    def test_vazio_e_ids_ausentes(self):
        heap = MinHeap(chave_medico)
        self.assertEqual(len(heap), 0)
        self.assertIsNone(heap.consultar_minimo())
        with self.assertRaises(IndexError):
            heap.extrair_minimo()
        for operacao in (heap.remover, heap.atualizar):
            with self.assertRaises(KeyError):
                operacao(1)
        self.conferir(heap)

    def test_pacientes_prioridade_chegada_e_id(self):
        heap = MinHeap(lambda p: p.chave_prioridade)
        pacientes = [self.paciente(4, 3), self.paciente(3, 1, 10),
                     self.paciente(2, 1), self.paciente(1, 1)]
        for paciente in pacientes:
            self.assertIsNone(heap.inserir(paciente))
            self.conferir(heap)
        for id in (1, 2, 3, 4):
            esperado = next(p for p in pacientes if p.id == id)
            self.assertIs(heap.consultar_minimo(), esperado)
            self.assertIs(heap.extrair_minimo(), esperado)
            self.conferir(heap)

    def test_medicos_carga_tempo_e_id(self):
        heap = MinHeap(chave_medico)
        medicos = [MedicoFicticio(1, 2), MedicoFicticio(2, 1, AGORA),
                   MedicoFicticio(4, 1, AGORA - timedelta(hours=1)),
                   MedicoFicticio(3, 1, AGORA - timedelta(hours=1)),
                   MedicoFicticio(6, 1), MedicoFicticio(5, 1), MedicoFicticio(7, 0, AGORA)]
        for medico in medicos:
            heap.inserir(medico)
        for id in (7, 5, 6, 3, 4, 2, 1):
            self.assertIs(heap.extrair_minimo(), next(m for m in medicos if m.id == id))
            self.conferir(heap)

    def test_tres_medicos_zerados_e_independencia_das_instancias(self):
        pacientes = MinHeap(lambda p: p.chave_prioridade)
        medicos = MinHeap(chave_medico)
        paciente = self.paciente(1)
        pacientes.inserir(paciente)
        for id in (3, 1, 2):
            medicos.inserir(MedicoFicticio(id))
        self.assertIsNot(pacientes._posicoes, medicos._posicoes)
        for id in (1, 2, 3):
            self.assertEqual(medicos.extrair_minimo().id, id)
        self.assertIs(pacientes.consultar_minimo(), paciente)
        self.conferir(pacientes)
        self.conferir(medicos)

    def test_reclassificacao_sobe_desce_sem_duplicar(self):
        heap = MinHeap(lambda p: p.chave_prioridade)
        pacientes = [self.paciente(id, 3) for id in range(1, 8)]
        for paciente in pacientes:
            heap.inserir(paciente)
        alvo = pacientes[-1]
        alvo.reclassificar(1)
        self.assertIsNone(heap.atualizar(alvo.id))
        self.assertIs(heap.consultar_minimo(), alvo)
        self.conferir(heap)
        alvo.reclassificar(5)
        heap.atualizar(alvo.id)
        self.assertIs(heap.consultar_minimo(), pacientes[0])
        self.assertEqual(len(heap), 7)
        self.conferir(heap)

    def test_atualiza_chave_medica_nas_duas_direcoes(self):
        heap = MinHeap(chave_medico)
        medicos = [MedicoFicticio(id) for id in (1, 2, 3)]
        for medico in medicos:
            heap.inserir(medico)
        medicos[0].ultima_atribuicao = AGORA
        heap.atualizar(1)
        self.assertIs(heap.consultar_minimo(), medicos[1])
        medicos[1].total_concluidos = 2
        heap.atualizar(2)
        self.assertIs(heap.consultar_minimo(), medicos[2])
        medicos[0].ultima_atribuicao = None
        heap.atualizar(1)
        self.assertIs(heap.consultar_minimo(), medicos[0])
        self.conferir(heap)

    def test_duplicacao_e_ausencia_nao_modificam_heap(self):
        heap = MinHeap(chave_medico)
        medico = MedicoFicticio(1)
        heap.inserir(medico)
        for duplicado in (medico, MedicoFicticio(1)):
            with self.assertRaises(ValueError):
                heap.inserir(duplicado)
        for operacao in (heap.remover, heap.atualizar):
            with self.assertRaises(KeyError):
                operacao(99)
        self.assertEqual(len(heap), 1)
        self.assertIs(heap.remover(1), medico)
        heap.inserir(medico)
        self.assertIs(heap.extrair_minimo(), medico)
        self.conferir(heap)

    def test_remove_raiz_meio_ultimo_e_reordena(self):
        for posicao in (0, 1, 3, 6):
            with self.subTest(posicao=posicao):
                heap = MinHeap(chave_medico)
                for id, carga in enumerate((1, 5, 2, 8, 9, 3, 4), start=1):
                    heap.inserir(MedicoFicticio(id, carga))
                alvo = heap._itens[posicao]
                restantes = sorted((m for m in heap._itens if m is not alvo), key=chave_medico)
                self.assertIs(heap.remover(alvo.id), alvo)
                self.assertIsNone(heap._posicoes.buscar(alvo.id))
                self.conferir(heap)
                for esperado in restantes:
                    self.assertIs(heap.extrair_minimo(), esperado)
                    self.conferir(heap)

    def test_sequencia_mista_com_colisoes_e_rehash_das_posicoes(self):
        rng = Random(17)
        heap = MinHeap(chave_medico)
        ativos = []
        for i in range(80):
            medico = MedicoFicticio((i + 1) * 176, rng.randrange(10))
            ativos.append(medico)
            heap.inserir(medico)
            self.conferir(heap)
        for _ in range(100):
            alvo = rng.choice(ativos)
            if rng.randrange(2):
                alvo.total_concluidos = rng.randrange(20)
                heap.atualizar(alvo.id)
            else:
                self.assertIs(heap.remover(alvo.id), alvo)
                ativos.remove(alvo)
            self.conferir(heap)
            self.assertIs(heap.consultar_minimo(), min(ativos, key=chave_medico))
        for esperado in sorted(ativos, key=chave_medico):
            self.assertIs(heap.extrair_minimo(), esperado)
            self.conferir(heap)

    def test_validar_detecta_corrupcoes(self):
        for caso in ("ordem", "posicao", "extra", "ausente", "duplicado", "id", "hash"):
            with self.subTest(caso=caso):
                heap = MinHeap(chave_medico)
                heap.inserir(MedicoFicticio(1))
                heap.inserir(MedicoFicticio(2))
                if caso == "ordem":
                    heap._itens[0].total_concluidos = 5
                elif caso == "posicao":
                    heap._posicoes.atualizar(1, 1)
                elif caso == "extra":
                    heap._posicoes.inserir(99, 2)
                elif caso == "ausente":
                    heap._posicoes.remover(1)
                elif caso == "duplicado":
                    heap._itens[1] = heap._itens[0]
                elif caso == "id":
                    heap._itens[0].id = True
                else:
                    heap._posicoes._quantidade = 99
                with self.assertRaises(ValueError):
                    heap.validar()

    def test_entradas_invalidas(self):
        with self.assertRaises(ValueError):
            MinHeap(None)
        heap = MinHeap(chave_medico)
        for item in (None, object(), MedicoFicticio(True)):
            with self.assertRaises(ValueError):
                heap.inserir(item)
        self.conferir(heap)

    def test_chave_incompativel_nao_insere_parcialmente(self):
        heap = MinHeap(chave_medico)
        original = MedicoFicticio(1)
        heap.inserir(original)
        with self.assertRaises(ValueError):
            heap.inserir(MedicoFicticio(2, "invalido"))
        self.assertEqual(len(heap), 1)
        self.assertIs(heap.consultar_minimo(), original)
        self.assertIsNone(heap._posicoes.buscar(2))
        self.conferir(heap)
