from datetime import datetime, timedelta, timezone
from unittest import TestCase

from atendimentos.domain.medico import Medico, SituacaoMedico
from atendimentos.structures.min_heap import MinHeap


INICIO = datetime(2026, 11, 26, 10, tzinfo=timezone.utc)


class MedicoTests(TestCase):
    def setUp(self):
        self.medico = Medico(1, "  Lia Prado  ", "  FICT-001  ")

    def estado(self, medico):
        return (medico.id, medico.nome, medico.registro, medico.situacao,
                medico.total_concluidos, medico.ultima_atribuicao, medico.chave_prioridade)

    def test_cadastro_normaliza_textos_e_inicia_disponivel(self):
        self.assertEqual(self.medico.nome, "Lia Prado")
        self.assertEqual(self.medico.registro, "FICT-001")
        self.assertEqual(self.medico.situacao, SituacaoMedico.DISPONIVEL)
        self.assertEqual(self.medico.total_concluidos, 0)
        self.assertIsNone(self.medico.ultima_atribuicao)
        self.assertEqual(str(self.medico), "1 - Lia Prado")

    def test_rejeita_ids_invalidos(self):
        for id in (0, -1, True, False, 1.5, "1", None):
            with self.subTest(id=id), self.assertRaises(ValueError):
                Medico(id, "Lia", "FICT-001")

    def test_rejeita_nomes_invalidos(self):
        for nome in ("", " \t\n", None, 123):
            with self.subTest(nome=nome), self.assertRaises(ValueError):
                Medico(1, nome, "FICT-001")

    def test_rejeita_registros_invalidos(self):
        for registro in ("", " \t\n", None, 123):
            with self.subTest(registro=registro), self.assertRaises(ValueError):
                Medico(1, "Lia", registro)

    def test_propriedades_nao_aceitam_atribuicao_direta(self):
        antes = self.estado(self.medico)
        for atributo, valor in (("id", 2), ("nome", "Outro"), ("registro", "Outro"),
                                ("situacao", SituacaoMedico.EM_ATENDIMENTO),
                                ("total_concluidos", 99), ("ultima_atribuicao", INICIO)):
            with self.subTest(atributo=atributo), self.assertRaises(AttributeError):
                setattr(self.medico, atributo, valor)
        self.assertEqual(self.estado(self.medico), antes)

    def test_inicio_normaliza_fuso_sem_incrementar_contador(self):
        local = INICIO.astimezone(timezone(timedelta(hours=-3)))
        self.assertIsNone(self.medico.iniciar_atendimento(local))
        self.assertEqual(self.medico.ultima_atribuicao, INICIO)
        self.assertIs(self.medico.ultima_atribuicao.tzinfo, timezone.utc)
        self.assertEqual(self.medico.situacao, SituacaoMedico.EM_ATENDIMENTO)
        self.assertEqual(self.medico.total_concluidos, 0)

    def test_inicio_invalido_preserva_todos_os_campos(self):
        self.medico.iniciar_atendimento(INICIO)
        self.medico.cancelar_atendimento()
        antes = self.estado(self.medico)
        for inicio in (None, "10:00", 123, datetime(2026, 11, 26),
                       datetime.min.replace(tzinfo=timezone.utc),
                       datetime.min.replace(tzinfo=timezone(timedelta(hours=1)))):
            with self.subTest(inicio=inicio), self.assertRaises(ValueError):
                self.medico.iniciar_atendimento(inicio)
            self.assertEqual(self.estado(self.medico), antes)

    def test_nao_inicia_medico_ocupado(self):
        self.medico.iniciar_atendimento(INICIO)
        antes = self.estado(self.medico)
        with self.assertRaises(ValueError):
            self.medico.iniciar_atendimento(INICIO + timedelta(hours=1))
        self.assertEqual(self.estado(self.medico), antes)

    def test_conclusao_incrementa_uma_vez_e_preserva_ultima_atribuicao(self):
        self.medico.iniciar_atendimento(INICIO)
        self.assertIsNone(self.medico.concluir_atendimento())
        self.assertEqual(self.medico.total_concluidos, 1)
        self.assertEqual(self.medico.situacao, SituacaoMedico.DISPONIVEL)
        self.assertEqual(self.medico.ultima_atribuicao, INICIO)
        antes = self.estado(self.medico)
        for operacao in (self.medico.concluir_atendimento, self.medico.cancelar_atendimento):
            with self.assertRaises(ValueError):
                operacao()
            self.assertEqual(self.estado(self.medico), antes)

    def test_cancelamento_libera_sem_incrementar(self):
        for total in (0, 1):
            self.medico.iniciar_atendimento(INICIO + timedelta(hours=total))
            atribuicao = self.medico.ultima_atribuicao
            self.assertIsNone(self.medico.cancelar_atendimento())
            self.assertEqual(self.medico.total_concluidos, total)
            self.assertEqual(self.medico.situacao, SituacaoMedico.DISPONIVEL)
            self.assertEqual(self.medico.ultima_atribuicao, atribuicao)
            antes = self.estado(self.medico)
            for operacao in (self.medico.cancelar_atendimento, self.medico.concluir_atendimento):
                with self.assertRaises(ValueError):
                    operacao()
                self.assertEqual(self.estado(self.medico), antes)
            self.medico.iniciar_atendimento(INICIO + timedelta(hours=total, minutes=30))
            self.medico.concluir_atendimento()
        self.assertEqual(self.medico.total_concluidos, 2)

    def test_medico_novo_nao_pode_encerrar(self):
        antes = self.estado(self.medico)
        for operacao in (self.medico.concluir_atendimento, self.medico.cancelar_atendimento):
            with self.assertRaises(ValueError):
                operacao()
            self.assertEqual(self.estado(self.medico), antes)

    def test_chave_prioriza_carga_antes_do_tempo(self):
        antigo = Medico(1, "Lia", "FICT-001")
        recente = Medico(2, "Rui", "FICT-002")
        antigo.iniciar_atendimento(INICIO)
        antigo.concluir_atendimento()
        recente.iniciar_atendimento(INICIO + timedelta(hours=1))
        recente.cancelar_atendimento()
        self.assertLess(recente.chave_prioridade, antigo.chave_prioridade)
        self.assertEqual(antigo.chave_prioridade, (1, INICIO, 1))

    def test_desempates_nunca_atribuido_tempo_e_id(self):
        nunca = Medico(9, "Nina", "FICT-009")
        antigo = Medico(3, "Lia", "FICT-003")
        recente = Medico(1, "Rui", "FICT-001")
        antigo.iniciar_atendimento(INICIO)
        antigo.cancelar_atendimento()
        recente.iniciar_atendimento(INICIO + timedelta(minutes=1))
        recente.cancelar_atendimento()
        self.assertLess(nunca.chave_prioridade, antigo.chave_prioridade)
        self.assertLess(antigo.chave_prioridade, recente.chave_prioridade)
        recente.iniciar_atendimento(INICIO)
        recente.cancelar_atendimento()
        self.assertLess(recente.chave_prioridade, antigo.chave_prioridade)
        self.assertLess(Medico(2, "Eva", "FICT-002").chave_prioridade, nunca.chave_prioridade)

    def test_heap_com_entidades_reais_preserva_identidade_e_reordena(self):
        heap = MinHeap(lambda medico: medico.chave_prioridade)
        medicos = [Medico(id, f"Médico {id}", f"FICT-{id:03}") for id in (3, 1, 2)]
        for medico in medicos:
            heap.inserir(medico)
        primeiro = heap.extrair_minimo()
        self.assertIs(primeiro, medicos[1])
        primeiro.iniciar_atendimento(INICIO)
        primeiro.concluir_atendimento()
        heap.inserir(primeiro)
        segundo = heap.extrair_minimo()
        self.assertIs(segundo, medicos[2])
        segundo.iniciar_atendimento(INICIO)
        segundo.cancelar_atendimento()
        heap.inserir(segundo)
        self.assertIs(heap.consultar_minimo(), medicos[0])
        # Apenas verifica atualizar(id); a coordenação pertence ao serviço futuro.
        primeiro.iniciar_atendimento(INICIO + timedelta(hours=1))
        primeiro.concluir_atendimento()
        heap.atualizar(primeiro.id)
        self.assertIsNone(heap.validar())
        self.assertEqual(len(heap), 3)
        for esperado in (medicos[0], segundo, primeiro):
            self.assertIs(heap.extrair_minimo(), esperado)
            heap.validar()
