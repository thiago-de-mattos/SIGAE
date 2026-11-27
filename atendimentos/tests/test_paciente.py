from datetime import datetime, timedelta, timezone
from unittest import TestCase

from atendimentos.domain.paciente import Paciente, SituacaoPaciente


class PacienteTests(TestCase):
    def setUp(self):
        self.chegada = datetime(2026, 11, 26, 11, 0, tzinfo=timezone.utc)
        self.paciente = Paciente(
            id=1,
            nome="  Ana Silva  ",
            chegada=self.chegada,
            prioridade=3,
        )

    def test_cadastro_inicia_aguardando_e_remove_espacos_do_nome(self):
        self.assertEqual(self.paciente.nome, "Ana Silva")
        self.assertEqual(
            self.paciente.situacao,
            SituacaoPaciente.AGUARDANDO,
        )

    def test_rejeita_ids_invalidos(self):
        for id_invalido in (0, -1, True, "1", 1.5):
            with self.subTest(id=id_invalido):
                with self.assertRaises(ValueError):
                    Paciente(id_invalido, "Ana", self.chegada, 3)

    def test_rejeita_nomes_invalidos(self):
        for nome in ("", "   ", None, 123):
            with self.subTest(nome=nome):
                with self.assertRaises(ValueError):
                    Paciente(1, nome, self.chegada, 3)

    def test_rejeita_chegada_invalida_ou_sem_fuso(self):
        for chegada in ("08:00", None, datetime(2026, 11, 26, 8, 0)):
            with self.subTest(chegada=chegada):
                with self.assertRaises(ValueError):
                    Paciente(1, "Ana", chegada, 3)

    def test_aceita_as_cinco_prioridades(self):
        for prioridade in range(1, 6):
            with self.subTest(prioridade=prioridade):
                paciente = Paciente(1, "Ana", self.chegada, prioridade)
                self.assertEqual(paciente.prioridade, prioridade)

    def test_rejeita_prioridades_invalidas(self):
        for prioridade in (0, 6, True, "1", 1.5, None):
            with self.subTest(prioridade=prioridade):
                with self.assertRaises(ValueError):
                    Paciente(1, "Ana", self.chegada, prioridade)

    def test_reclassificacao_preserva_identidade_e_chegada(self):
        self.paciente.reclassificar(1)

        self.assertEqual(self.paciente.prioridade, 1)
        self.assertEqual(self.paciente.id, 1)
        self.assertEqual(self.paciente.chegada, self.chegada)
        self.assertEqual(
            self.paciente.situacao,
            SituacaoPaciente.AGUARDANDO,
        )

    def test_reclassificacao_invalida_preserva_prioridade(self):
        with self.assertRaises(ValueError):
            self.paciente.reclassificar(6)

        self.assertEqual(self.paciente.prioridade, 3)

    def test_emergencia_tem_preferencia_mesmo_chegando_depois(self):
        emergencia = Paciente(
            2,
            "Bruno",
            self.chegada + timedelta(minutes=10),
            1,
        )

        self.assertLess(
            emergencia.chave_prioridade,
            self.paciente.chave_prioridade,
        )
        self.assertLess(
            self.paciente.chave_chegada,
            emergencia.chave_chegada,
        )

    def test_empate_de_prioridade_considera_chegada_e_depois_id(self):
        mais_tarde = Paciente(
            2,
            "Bruno",
            self.chegada + timedelta(minutes=1),
            3,
        )
        mesmo_horario = Paciente(3, "Carla", self.chegada, 3)

        self.assertLess(
            self.paciente.chave_prioridade,
            mais_tarde.chave_prioridade,
        )
        self.assertLess(
            self.paciente.chave_prioridade,
            mesmo_horario.chave_prioridade,
        )
        self.assertLess(
            self.paciente.chave_chegada,
            mesmo_horario.chave_chegada,
        )

    def test_fluxo_de_atendimento_e_conclusao(self):
        self.paciente.iniciar_atendimento()
        self.assertEqual(
            self.paciente.situacao,
            SituacaoPaciente.EM_ATENDIMENTO,
        )

        self.paciente.concluir_atendimento()
        self.assertEqual(
            self.paciente.situacao,
            SituacaoPaciente.CONCLUIDO,
        )

        with self.assertRaises(ValueError):
            self.paciente.concluir_atendimento()

    def test_nao_conclui_paciente_aguardando(self):
        with self.assertRaises(ValueError):
            self.paciente.concluir_atendimento()

        self.assertEqual(
            self.paciente.situacao,
            SituacaoPaciente.AGUARDANDO,
        )

    def test_nao_reclassifica_nem_inicia_novamente_paciente_em_atendimento(self):
        self.paciente.iniciar_atendimento()

        with self.assertRaises(ValueError):
            self.paciente.reclassificar(1)

        with self.assertRaises(ValueError):
            self.paciente.iniciar_atendimento()

        self.assertEqual(self.paciente.prioridade, 3)

    def test_cancela_espera_ou_atendimento(self):
        for em_atendimento in (False, True):
            with self.subTest(em_atendimento=em_atendimento):
                paciente = Paciente(1, "Ana", self.chegada, 3)

                if em_atendimento:
                    paciente.iniciar_atendimento()

                paciente.cancelar()

                self.assertEqual(
                    paciente.situacao,
                    SituacaoPaciente.CANCELADO,
                )

                with self.assertRaises(ValueError):
                    paciente.cancelar()

                with self.assertRaises(ValueError):
                    paciente.iniciar_atendimento()

    def test_nao_cancela_nem_reclassifica_paciente_concluido(self):
        self.paciente.iniciar_atendimento()
        self.paciente.concluir_atendimento()

        with self.assertRaises(ValueError):
            self.paciente.cancelar()

        with self.assertRaises(ValueError):
            self.paciente.reclassificar(1)

    def test_id_e_chegada_nao_aceitam_atribuicao_direta(self):
        with self.assertRaises(AttributeError):
            self.paciente.id = 2

        with self.assertRaises(AttributeError):
            self.paciente.chegada = self.chegada + timedelta(minutes=1)