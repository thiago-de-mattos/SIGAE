from datetime import datetime, timedelta, timezone
from unittest import TestCase

from atendimentos.domain.atendimento import Atendimento, SituacaoAtendimento
from atendimentos.domain.medico import Medico
from atendimentos.domain.paciente import Paciente


class AtendimentoTests(TestCase):
    def setUp(self):
        self.inicio = datetime(2026, 11, 26, 10, tzinfo=timezone.utc)
        self.fim = self.inicio + timedelta(minutes=30)
        self.paciente = Paciente(1, "Ana Lima", self.inicio, 3)
        self.medico = Medico(2, "Lia Prado", "FICT-002")

    def criar(self):
        return Atendimento(3, self.paciente, self.medico, self.inicio)

    def estado(self, atendimento):
        return (atendimento.id, atendimento.paciente, atendimento.medico,
                atendimento.inicio, atendimento.fim, atendimento.situacao)

    def estado_entidades(self):
        return (
            self.paciente.id, self.paciente.nome, self.paciente.chegada,
            self.paciente.prioridade, self.paciente.situacao,
            self.medico.id, self.medico.nome, self.medico.registro,
            self.medico.situacao, self.medico.total_concluidos,
            self.medico.ultima_atribuicao,
        )

    def test_atributos_iniciais_e_identidade(self):
        atendimento = self.criar()
        self.assertEqual(atendimento.id, 3)
        self.assertIs(atendimento.paciente, self.paciente)
        self.assertIs(atendimento.medico, self.medico)
        self.assertIs(atendimento.inicio, self.inicio)
        self.assertIsNone(atendimento.fim)
        self.assertEqual(atendimento.situacao, SituacaoAtendimento.EM_ATENDIMENTO)
        self.assertEqual(str(atendimento), "3 - Ana Lima / Lia Prado")

    def test_rejeita_ids_invalidos(self):
        for id in (0, -1, True, False, 1.5, "1", None):
            with self.subTest(id=id), self.assertRaises(ValueError):
                Atendimento(id, self.paciente, self.medico, self.inicio)

    def test_rejeita_referencias_invalidas(self):
        for paciente in (None, 1, "Ana", object(), self.medico):
            with self.subTest(paciente=paciente), self.assertRaises(ValueError):
                Atendimento(3, paciente, self.medico, self.inicio)
        for medico in (None, 2, "Lia", object(), self.paciente):
            with self.subTest(medico=medico), self.assertRaises(ValueError):
                Atendimento(3, self.paciente, medico, self.inicio)

    def test_rejeita_inicio_invalido_sem_efeitos_colaterais(self):
        antes = self.estado_entidades()
        for inicio in (None, "10:00", 123, self.inicio.replace(tzinfo=None)):
            with self.subTest(inicio=inicio), self.assertRaises(ValueError):
                Atendimento(3, self.paciente, self.medico, inicio)
            self.assertEqual(self.estado_entidades(), antes)

    def test_propriedades_nao_aceitam_atribuicao_direta(self):
        atendimento = self.criar()
        antes = self.estado(atendimento)
        for atributo, valor in (("id", 9), ("paciente", None), ("medico", None),
                                ("inicio", self.fim), ("fim", self.fim),
                                ("situacao", SituacaoAtendimento.CONCLUIDO)):
            with self.subTest(atributo=atributo), self.assertRaises(AttributeError):
                setattr(atendimento, atributo, valor)
        self.assertEqual(self.estado(atendimento), antes)

    def test_conclusao_e_cancelamento_preservam_atributos(self):
        for metodo, situacao in (("concluir", SituacaoAtendimento.CONCLUIDO),
                                ("cancelar", SituacaoAtendimento.CANCELADO)):
            with self.subTest(metodo=metodo):
                atendimento = self.criar()
                self.assertIsNone(getattr(atendimento, metodo)(self.fim))
                self.assertEqual(atendimento.situacao, situacao)
                self.assertIs(atendimento.fim, self.fim)
                self.assertEqual(atendimento.id, 3)
                self.assertIs(atendimento.inicio, self.inicio)
                self.assertIs(atendimento.paciente, self.paciente)
                self.assertIs(atendimento.medico, self.medico)

    def test_rejeita_todas_as_transicoes_apos_encerramento(self):
        for primeiro in ("concluir", "cancelar"):
            for segundo in ("concluir", "cancelar"):
                with self.subTest(primeiro=primeiro, segundo=segundo):
                    atendimento = self.criar()
                    getattr(atendimento, primeiro)(self.fim)
                    antes = self.estado(atendimento)
                    with self.assertRaises(ValueError):
                        getattr(atendimento, segundo)(self.fim + timedelta(hours=1))
                    self.assertEqual(self.estado(atendimento), antes)

    def test_fim_invalido_preserva_estado_e_permite_tentativa_valida(self):
        for metodo in ("concluir", "cancelar"):
            for fim in (None, "10:30", 123, self.fim.replace(tzinfo=None),
                        self.inicio - timedelta(microseconds=1)):
                with self.subTest(metodo=metodo, fim=fim):
                    atendimento = self.criar()
                    antes = self.estado(atendimento)
                    with self.assertRaises(ValueError):
                        getattr(atendimento, metodo)(fim)
                    self.assertEqual(self.estado(atendimento), antes)
                    getattr(atendimento, metodo)(self.fim)

    def test_encerramento_no_mesmo_instante_com_outro_fuso(self):
        for metodo in ("concluir", "cancelar"):
            with self.subTest(metodo=metodo):
                atendimento = self.criar()
                fim = self.inicio.astimezone(timezone(timedelta(hours=-3)))
                getattr(atendimento, metodo)(fim)
                self.assertEqual(atendimento.fim, atendimento.inicio)
                self.assertIs(atendimento.inicio, self.inicio)

    def test_fim_anterior_em_outro_fuso_e_rejeitado(self):
        atendimento = self.criar()
        fim = (self.inicio - timedelta(minutes=1)).astimezone(timezone(timedelta(hours=3)))
        with self.assertRaises(ValueError):
            atendimento.concluir(fim)
        self.assertIsNone(atendimento.fim)
        self.assertEqual(atendimento.situacao, SituacaoAtendimento.EM_ATENDIMENTO)

    def test_criacao_e_encerramento_nao_modificam_entidades(self):
        # Exercita entidades tanto antes quanto depois da coordenação externa.
        for em_atendimento in (False, True):
            if em_atendimento:
                self.paciente.iniciar_atendimento()
                self.medico.iniciar_atendimento(self.inicio)
            for metodo in ("concluir", "cancelar"):
                with self.subTest(em_atendimento=em_atendimento, metodo=metodo):
                    antes = self.estado_entidades()
                    atendimento = self.criar()
                    self.assertEqual(self.estado_entidades(), antes)
                    with self.assertRaises(ValueError):
                        getattr(atendimento, metodo)(self.inicio - timedelta(minutes=1))
                    self.assertEqual(self.estado_entidades(), antes)
                    getattr(atendimento, metodo)(self.fim)
                    self.assertEqual(self.estado_entidades(), antes)
                    with self.assertRaises(ValueError):
                        getattr(atendimento, metodo)(self.fim)
                    self.assertEqual(self.estado_entidades(), antes)

    def test_referencias_compartilhadas_nao_sao_copias(self):
        atendimento = self.criar()
        self.paciente.reclassificar(1)
        self.medico.iniciar_atendimento(self.inicio)
        self.assertEqual(atendimento.paciente.prioridade, 1)
        self.assertEqual(atendimento.medico.ultima_atribuicao, self.inicio)
        atendimento.cancelar(self.fim)
        self.assertIs(atendimento.paciente, self.paciente)
        self.assertIs(atendimento.medico, self.medico)
