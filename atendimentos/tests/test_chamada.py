from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from atendimentos.domain.medico import SituacaoMedico
from atendimentos.domain.paciente import SituacaoPaciente
from atendimentos.domain.atendimento import SituacaoAtendimento
from atendimentos.services.sistema_atendimento import SistemaAtendimento


INICIO = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)


class ChamadaTests(TestCase):
    def preparar(self, quantidade=7):
        sistema = SistemaAtendimento()
        pacientes = [sistema.cadastrar_paciente(f"Paciente {i}", INICIO, 3)
                     for i in range(quantidade)]
        medicos = [sistema.cadastrar_medico(f"Médico {i}", f"FICTICIO-{i}")
                   for i in range(quantidade)]
        return sistema, pacientes, medicos

    def conferir(self, sistema):
        for estrutura in (sistema._pacientes, sistema._medicos, sistema._atendimentos,
                          sistema._heap_pacientes, sistema._heap_medicos, sistema._arvore_espera):
            estrutura.validar()
        espera = [p for p in sistema.listar_pacientes() if p.situacao == SituacaoPaciente.AGUARDANDO]
        disponiveis = [m for m in sistema.listar_medicos() if m.situacao == SituacaoMedico.DISPONIVEL]
        self.assertEqual(sistema.listar_fila(), sorted(espera, key=lambda p: p.chave_chegada))
        for heap, registros in ((sistema._heap_pacientes, espera), (sistema._heap_medicos, disponiveis)):
            self.assertEqual(len(heap), len(registros))
            for registro in registros:
                posicao = heap._posicoes.buscar(registro.id)
                self.assertIsNotNone(posicao)
                self.assertIs(heap._itens[posicao], registro)
            self.assertIs(heap.consultar_minimo(), min(registros, key=lambda r: r.chave_prioridade, default=None))
        atendimentos = sistema._atendimentos.listar_valores()
        for atendimento in atendimentos:
            self.assertIs(sistema.buscar_paciente(atendimento.paciente.id), atendimento.paciente)
            self.assertIs(sistema.buscar_medico(atendimento.medico.id), atendimento.medico)
            self.assertEqual(atendimento.situacao, SituacaoAtendimento.EM_ATENDIMENTO)
            self.assertEqual(atendimento.paciente.situacao, SituacaoPaciente.EM_ATENDIMENTO)
            self.assertEqual(atendimento.medico.situacao, SituacaoMedico.EM_ATENDIMENTO)
            self.assertEqual(sum(a.paciente is atendimento.paciente for a in atendimentos), 1)
            self.assertEqual(sum(a.medico is atendimento.medico for a in atendimentos), 1)

    def test_chamada_preserva_referencias_registra_horario_e_nao_incrementa_conclusoes(self):
        sistema, pacientes, medicos = self.preparar()
        inicio = INICIO.astimezone(timezone(timedelta(hours=-3)))
        atendimento = sistema.chamar_proximo(inicio)
        self.assertEqual(atendimento.id, 1)
        self.assertIs(atendimento.paciente, pacientes[0])
        self.assertIs(atendimento.medico, medicos[0])
        self.assertIs(atendimento.inicio, inicio)
        self.assertIsNone(atendimento.fim)
        self.assertIs(sistema._atendimentos.buscar(1), atendimento)
        self.assertEqual(medicos[0].ultima_atribuicao, INICIO)
        self.assertEqual(medicos[0].total_concluidos, 0)
        self.assertEqual(len(sistema._pacientes), 7)
        self.assertEqual(len(sistema._medicos), 7)
        self.conferir(sistema)

    def test_horario_padrao_possui_fuso(self):
        sistema, _, _ = self.preparar(1)
        antes = datetime.now(timezone.utc)
        atendimento = sistema.chamar_proximo()
        self.assertLessEqual(antes, atendimento.inicio)
        self.assertLessEqual(atendimento.inicio, datetime.now(timezone.utc))
        self.conferir(sistema)

    def test_prioridade_clinica_chegada_e_id(self):
        sistema, pacientes, _ = self.preparar(4)
        sistema.reclassificar_paciente(pacientes[0].id, 5)
        tardio = sistema.cadastrar_paciente("Mais tarde", INICIO + timedelta(minutes=1), 1)
        sistema.cadastrar_medico("Extra", "FICTICIO-EXTRA")
        sistema.reclassificar_paciente(pacientes[2].id, 1)
        sistema.reclassificar_paciente(pacientes[3].id, 1)
        for paciente in (pacientes[2], pacientes[3], tardio, pacientes[1], pacientes[0]):
            self.assertIs(sistema.chamar_proximo(INICIO + timedelta(hours=1)).paciente, paciente)
            self.conferir(sistema)

    def test_tres_medicos_zerados_e_exclusao_dos_ocupados(self):
        sistema, pacientes, medicos = self.preparar(3)
        for id, medico in enumerate(medicos, 1):
            atendimento = sistema.chamar_proximo(INICIO)
            self.assertIs(atendimento.medico, medico)
            self.assertEqual(atendimento.id, id)
            self.assertEqual(medico.total_concluidos, 0)
            self.conferir(sistema)
        sistema.cadastrar_paciente("Espera", INICIO, 1)
        with self.assertRaises(ValueError):
            sistema.chamar_proximo(INICIO)
        self.assertEqual(sistema._ultimo_id_atendimento, 3)
        self.conferir(sistema)

    def test_selecao_medica_por_carga_atribuicao_e_id(self):
        sistema, _, medicos = self.preparar(6)
        # Preparação de cargas anteriores pelas entidades, sem APIs futuras do serviço.
        for medico, carga, minutos in zip(medicos, (2, 1, 0, 0, 0, 0), (0, 1, 2, 2, 3, None)):
            sistema._heap_medicos.remover(medico.id)
            for _ in range(carga):
                medico.iniciar_atendimento(INICIO - timedelta(days=1))
                medico.concluir_atendimento()
            if minutos is not None:
                medico.iniciar_atendimento(INICIO + timedelta(minutes=minutos))
                medico.cancelar_atendimento()
            sistema._heap_medicos.inserir(medico)
        for indice in (5, 2, 3, 4, 1, 0):
            medico = medicos[indice]
            carga = medico.total_concluidos
            self.assertIs(sistema.chamar_proximo(INICIO + timedelta(hours=1)).medico, medico)
            self.assertEqual(medico.total_concluidos, carga)
            self.conferir(sistema)

    def test_ausencia_preserva_estado_e_consulta_ambos_minimos(self):
        for tem_paciente, tem_medico in ((False, False), (False, True), (True, False)):
            with self.subTest(paciente=tem_paciente, medico=tem_medico):
                sistema = SistemaAtendimento()
                if tem_paciente:
                    sistema.cadastrar_paciente("Ana", INICIO, 2)
                if tem_medico:
                    sistema.cadastrar_medico("Bia", "FICTICIO")
                fila = sistema.listar_fila()
                raiz = sistema._arvore_espera._raiz
                with patch.object(sistema._heap_pacientes, "consultar_minimo", wraps=sistema._heap_pacientes.consultar_minimo) as p, patch.object(sistema._heap_medicos, "consultar_minimo", wraps=sistema._heap_medicos.consultar_minimo) as m:
                    with self.assertRaises(ValueError):
                        sistema.chamar_proximo(INICIO)
                    p.assert_called_once_with()
                    m.assert_called_once_with()
                self.assertEqual(sistema.listar_fila(), fila)
                self.assertIs(sistema._arvore_espera._raiz, raiz)
                self.assertEqual(sistema._ultimo_id_atendimento, 0)
                self.conferir(sistema)

    def test_ambos_minimos_sao_consultados_antes_da_primeira_mutacao(self):
        sistema, _, _ = self.preparar()
        remover = sistema._heap_pacientes.remover
        with patch.object(sistema._heap_pacientes, "consultar_minimo", wraps=sistema._heap_pacientes.consultar_minimo) as p, patch.object(sistema._heap_medicos, "consultar_minimo", wraps=sistema._heap_medicos.consultar_minimo) as m:
            def conferir_antes(id):
                p.assert_called_once_with()
                m.assert_called_once_with()
                self.assertEqual(sistema._ultimo_id_atendimento, 1)
                return remover(id)
            with patch.object(sistema._heap_pacientes, "remover", side_effect=conferir_antes):
                sistema.chamar_proximo(INICIO)
        self.conferir(sistema)

    def test_horarios_invalidos_nao_mutam_indices_ou_reservam_id(self):
        for inicio in ("hoje", True, 1, datetime(2026, 1, 1),
                       datetime.min.replace(tzinfo=timezone.utc),
                       datetime.min.replace(tzinfo=timezone(timedelta(hours=1)))):
            with self.subTest(inicio=inicio):
                sistema, pacientes, medicos = self.preparar()
                with patch.object(sistema._heap_pacientes, "remover") as remover:
                    with self.assertRaises(ValueError):
                        sistema.chamar_proximo(inicio)
                    remover.assert_not_called()
                self.assertEqual(sistema._ultimo_id_atendimento, 0)
                self.assertIsNone(medicos[0].ultima_atribuicao)
                self.conferir(sistema)

    def test_estados_incompativeis_sao_rejeitados_sem_mutacao(self):
        for alvo in ("paciente", "medico"):
            sistema, pacientes, medicos = self.preparar(1)
            if alvo == "paciente":
                pacientes[0].iniciar_atendimento()
            else:
                medicos[0].iniciar_atendimento(INICIO)
            antes = (pacientes[0].situacao, medicos[0].situacao, medicos[0].ultima_atribuicao)
            with self.assertRaises(ValueError):
                sistema.chamar_proximo(INICIO)
            self.assertEqual(antes, (pacientes[0].situacao, medicos[0].situacao, medicos[0].ultima_atribuicao))
            self.assertEqual(len(sistema._heap_pacientes), 1)
            self.assertEqual(len(sistema._heap_medicos), 1)
            self.assertEqual(sistema._ultimo_id_atendimento, 0)

    def test_falhas_antes_e_depois_de_cada_mutacao_restauram_estado(self):
        for etapa in range(6):
            for depois in (False, True):
                with self.subTest(etapa=etapa, depois=depois):
                    sistema, pacientes, medicos = self.preparar()
                    # Todos já atribuídos; restaurar também um horário não nulo.
                    for medico in medicos:
                        medico.iniciar_atendimento(INICIO - timedelta(hours=1))
                        medico.cancelar_atendimento()
                        sistema._heap_medicos.atualizar(medico.id)
                    alvos = ((sistema._heap_pacientes, "remover"),
                             (sistema._arvore_espera, "remover"),
                             (sistema._heap_medicos, "remover"),
                             (pacientes[0], "iniciar_atendimento"),
                             (medicos[0], "iniciar_atendimento"),
                             (sistema._atendimentos, "inserir"))
                    objeto, nome = alvos[etapa]
                    original = getattr(objeto, nome)
                    erro = RuntimeError("falha injetada")
                    chamadas = []

                    def falhar_uma_vez(*args):
                        chamadas.append(args)
                        if len(chamadas) == 1:
                            if depois:
                                original(*args)
                            raise erro
                        return original(*args)

                    with patch.object(objeto, nome, side_effect=falhar_uma_vez):
                        with self.assertRaises(RuntimeError) as capturado:
                            sistema.chamar_proximo(INICIO)
                    self.assertIs(capturado.exception, erro)
                    self.assertEqual(len(sistema._atendimentos), 0)
                    self.assertEqual(sistema._ultimo_id_atendimento, 1)
                    self.assertEqual(sistema._ultimo_id_paciente, 7)
                    self.assertEqual(sistema._ultimo_id_medico, 7)
                    self.assertTrue(all(m.ultima_atribuicao == INICIO - timedelta(hours=1) for m in medicos))
                    self.assertTrue(all(m.total_concluidos == 0 for m in medicos))
                    self.conferir(sistema)
                    atendimento = sistema.chamar_proximo(INICIO)
                    self.assertEqual(atendimento.id, 2)
                    self.assertIs(atendimento.paciente, pacientes[0])
                    self.assertIs(atendimento.medico, medicos[0])
                    self.conferir(sistema)

    def test_falha_de_recuperacao_explicita_e_demais_compensacoes_executadas(self):
        sistema, pacientes, medicos = self.preparar()
        erro = RuntimeError("registro")
        recuperacao = RuntimeError("reinsercao")
        with patch.object(sistema._atendimentos, "inserir", side_effect=erro), patch.object(sistema._heap_medicos, "inserir", side_effect=recuperacao):
            with self.assertRaises(ExceptionGroup) as capturado:
                sistema.chamar_proximo(INICIO)
        self.assertIn(erro, capturado.exception.exceptions)
        self.assertIn(recuperacao, capturado.exception.exceptions)
        self.assertEqual(pacientes[0].situacao, SituacaoPaciente.AGUARDANDO)
        self.assertEqual(medicos[0].situacao, SituacaoMedico.DISPONIVEL)
        self.assertIsNone(medicos[0].ultima_atribuicao)
        self.assertEqual(len(sistema._heap_pacientes), 7)
        self.assertEqual(len(sistema._arvore_espera), 7)
        self.assertEqual(sistema._ultimo_id_atendimento, 1)

    def test_falha_apos_rehash_preserva_atendimentos_anteriores(self):
        sistema, pacientes, medicos = self.preparar(12)
        anteriores = [sistema.chamar_proximo(INICIO) for _ in range(8)]
        inserir = sistema._atendimentos.inserir

        def falhar_apos_inserir(id, atendimento):
            inserir(id, atendimento)
            raise RuntimeError("após expansão")

        with patch.object(sistema._atendimentos, "inserir", side_effect=falhar_apos_inserir):
            with self.assertRaises(RuntimeError):
                sistema.chamar_proximo(INICIO)
        self.assertEqual(len(sistema._atendimentos), 8)
        for atendimento in anteriores:
            self.assertIs(sistema._atendimentos.buscar(atendimento.id), atendimento)
        self.assertIsNone(medicos[8].ultima_atribuicao)
        self.assertEqual(pacientes[8].situacao, SituacaoPaciente.AGUARDANDO)
        self.conferir(sistema)
        novo = sistema.chamar_proximo(INICIO)
        self.assertEqual(novo.id, 10)
        self.assertIs(novo.paciente, pacientes[8])
        self.assertIs(novo.medico, medicos[8])
        self.conferir(sistema)

    def test_referencias_ausentes_dos_indices_impedem_chamada(self):
        for indice in ("pacientes", "medicos", "arvore"):
            with self.subTest(indice=indice):
                sistema, pacientes, medicos = self.preparar(1)
                if indice == "pacientes":
                    sistema._pacientes.remover(pacientes[0].id)
                elif indice == "medicos":
                    sistema._medicos.remover(medicos[0].id)
                else:
                    sistema._arvore_espera.remover(pacientes[0].chave_chegada)
                with self.assertRaises(ValueError):
                    sistema.chamar_proximo(INICIO)
                self.assertEqual(sistema._ultimo_id_atendimento, 0)
                self.assertEqual(pacientes[0].situacao, SituacaoPaciente.AGUARDANDO)
                self.assertEqual(medicos[0].situacao, SituacaoMedico.DISPONIVEL)
                self.assertEqual(len(sistema._heap_pacientes), 1)
                self.assertEqual(len(sistema._heap_medicos), 1)
