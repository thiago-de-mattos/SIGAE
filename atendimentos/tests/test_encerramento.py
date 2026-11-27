from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from atendimentos.domain.atendimento import Atendimento, SituacaoAtendimento
from atendimentos.domain.medico import SituacaoMedico
from atendimentos.domain.paciente import SituacaoPaciente
from atendimentos.services.sistema_atendimento import SistemaAtendimento, SistemaIndisponivel


INICIO = datetime(2026, 1, 1, tzinfo=timezone.utc)
FIM = INICIO + timedelta(hours=1)


class EncerramentoTests(TestCase):
    def preparar(self):
        s = SistemaAtendimento()
        for i in range(10):
            s.cadastrar_paciente(f"Paciente {i}", INICIO, 3)
        for i in range(3):
            s.cadastrar_medico(f"Médico {i}", f"FICTICIO-{i}")
        return s

    def conferir(self, s):
        for indice in (s._pacientes, s._medicos, s._atendimentos,
                       s._arvore_espera, s._heap_pacientes, s._heap_medicos):
            indice.validar()
        pacientes, medicos = s.listar_pacientes(), s.listar_medicos()
        espera = [p for p in pacientes if p.situacao == SituacaoPaciente.AGUARDANDO]
        livres = [m for m in medicos if m.situacao == SituacaoMedico.DISPONIVEL]
        self.assertEqual(s.listar_fila(), sorted(espera, key=lambda p: p.chave_chegada))
        for heap, registros in ((s._heap_pacientes, espera), (s._heap_medicos, livres)):
            self.assertEqual(len(heap), len(registros))
            for registro in registros:
                pos = heap._posicoes.buscar(registro.id)
                self.assertIsNotNone(pos)
                self.assertIs(heap._itens[pos], registro)
        atendimentos = s._atendimentos.listar_valores()
        for a in atendimentos:
            self.assertIs(s.buscar_paciente(a.paciente.id), a.paciente)
            self.assertIs(s.buscar_medico(a.medico.id), a.medico)
            if a.situacao == SituacaoAtendimento.EM_ATENDIMENTO:
                self.assertEqual(a.paciente.situacao, SituacaoPaciente.EM_ATENDIMENTO)
                self.assertEqual(a.medico.situacao, SituacaoMedico.EM_ATENDIMENTO)
                self.assertIsNone(a.fim)
            else:
                self.assertEqual(a.paciente.situacao.value, a.situacao.value)
                self.assertGreaterEqual(a.fim, a.inicio)
        for m in medicos:
            ativos = [a for a in atendimentos if a.medico is m and a.situacao == SituacaoAtendimento.EM_ATENDIMENTO]
            self.assertEqual(len(ativos), int(m.situacao == SituacaoMedico.EM_ATENDIMENTO))
            self.assertEqual(m.total_concluidos, sum(a.medico is m and a.situacao == SituacaoAtendimento.CONCLUIDO for a in atendimentos))

    def retrato(self, s):
        return ([(p, p.situacao) for p in s.listar_pacientes()],
                [(m, m.situacao, m.total_concluidos, m.ultima_atribuicao) for m in s.listar_medicos()],
                [(a, a.situacao, a.fim) for a in s._atendimentos.listar_valores()],
                s.listar_fila(), s._ultimo_id_atendimento)

    def test_conclusao_e_cancelamento_ativos_preservam_referencias(self):
        for concluir in (False, True):
            s = self.preparar()
            a = s.chamar_proximo(INICIO)
            if concluir:
                self.assertIs(s.concluir_atendimento(a.id, FIM), a)
            else:
                self.assertIs(s.cancelar_paciente(a.paciente.id, FIM), a.paciente)
            self.assertIs(s._atendimentos.buscar(a.id), a)
            self.assertIs(a.fim, FIM)
            self.assertEqual(a.medico.ultima_atribuicao, INICIO)
            self.assertEqual(a.medico.total_concluidos, int(concluir))
            self.assertEqual(a.situacao, SituacaoAtendimento.CONCLUIDO if concluir else SituacaoAtendimento.CANCELADO)
            self.conferir(s)

    def test_cancelamento_na_espera_nao_cria_atendimento(self):
        s = self.preparar()
        p = s.buscar_paciente(4)
        self.assertIs(s.cancelar_paciente(p.id, FIM), p)
        self.assertEqual(p.situacao, SituacaoPaciente.CANCELADO)
        self.assertEqual(len(s._atendimentos), 0)
        self.assertEqual(s._ultimo_id_atendimento, 0)
        self.conferir(s)

    def test_horario_automatico_e_igual_ao_inicio(self):
        s = self.preparar()
        a = s.chamar_proximo(INICIO)
        s.concluir_atendimento(a.id, INICIO)
        self.assertEqual(a.fim, INICIO)
        b = s.chamar_proximo(INICIO)
        s.cancelar_paciente(b.paciente.id)
        self.assertIsNotNone(b.fim.utcoffset())
        c = s.chamar_proximo(INICIO)
        s.concluir_atendimento(c.id)
        self.assertIsNotNone(c.fim.utcoffset())
        s.cancelar_paciente(5)
        self.conferir(s)

    def test_repeticoes_e_operacoes_cruzadas_nao_tem_efeitos(self):
        for concluir in (True, False):
            s = self.preparar()
            a = s.chamar_proximo(INICIO)
            if concluir:
                s.concluir_atendimento(a.id, FIM)
            else:
                s.cancelar_paciente(a.paciente.id, FIM)
            antes = self.retrato(s)
            for operacao, id in ((s.concluir_atendimento, a.id), (s.cancelar_paciente, a.paciente.id)):
                with self.assertRaises(ValueError):
                    operacao(id, FIM)
                self.assertEqual(self.retrato(s), antes)
            self.conferir(s)
        s = self.preparar()
        s.cancelar_paciente(1, FIM)
        with self.assertRaises(ValueError):
            s.cancelar_paciente(1, FIM)
        self.conferir(s)

    def test_ids_e_horarios_invalidos_sem_efeitos(self):
        s = self.preparar()
        a = s.chamar_proximo(INICIO)
        antes = self.retrato(s)
        for operacao in (s.concluir_atendimento, s.cancelar_paciente):
            for id in (999, True, '1', None, 1.5):
                with self.subTest(id=id), self.assertRaises((ValueError, KeyError)):
                    operacao(id, FIM)
                self.assertEqual(self.retrato(s), antes)
        for operacao, id in ((s.concluir_atendimento, a.id), (s.cancelar_paciente, a.paciente.id), (s.cancelar_paciente, 2)):
            for fim in ('agora', True, datetime(2026, 1, 1), INICIO - timedelta(seconds=1)):
                with self.subTest(fim=fim), self.assertRaises(ValueError):
                    operacao(id, fim)
                self.assertEqual(self.retrato(s), antes)
        self.conferir(s)

    def test_menor_carga_apos_conclusoes(self):
        s = self.preparar()
        a, b, c = [s.chamar_proximo(INICIO) for _ in range(3)]
        s.concluir_atendimento(a.id, FIM)
        s.cancelar_paciente(b.paciente.id, FIM)
        s.concluir_atendimento(c.id, FIM)
        self.assertIs(s.chamar_proximo(FIM).medico, b.medico)
        self.assertIs(s.chamar_proximo(FIM).medico, a.medico)
        self.conferir(s)

    def test_desempate_por_ultima_atribuicao_apos_cancelamento(self):
        s = self.preparar()
        a = s.chamar_proximo(INICIO)
        b = s.chamar_proximo(INICIO + timedelta(minutes=1))
        c = s.chamar_proximo(INICIO + timedelta(minutes=2))
        for atendimento in (c, b, a):
            s.cancelar_paciente(atendimento.paciente.id, FIM)
        for esperado in (a.medico, b.medico, c.medico):
            self.assertIs(s.chamar_proximo(FIM).medico, esperado)
        self.conferir(s)

    def test_vinculo_ativo_ausente_duplicado_e_estados_incompativeis(self):
        for caso in ('ausente', 'duplicado', 'medico', 'paciente'):
            s = self.preparar()
            a = s.chamar_proximo(INICIO)
            if caso == 'ausente':
                s._atendimentos.remover(a.id)
            elif caso == 'duplicado':
                s._atendimentos.inserir(99, Atendimento(99, a.paciente, a.medico, INICIO))
            elif caso == 'medico':
                a.medico.cancelar_atendimento()
            else:
                a.paciente.cancelar()
            antes = self.retrato(s)
            with self.assertRaises(ValueError):
                if caso == 'paciente':
                    s.concluir_atendimento(a.id, FIM)
                else:
                    s.cancelar_paciente(a.paciente.id, FIM)
            self.assertEqual(self.retrato(s), antes)

    def test_falhas_antes_e_depois_de_todas_mutacoes_ativas(self):
        for concluir in (False, True):
            for etapa in range(4):
                for depois in (False, True):
                    with self.subTest(concluir=concluir, etapa=etapa, depois=depois):
                        s = self.preparar()
                        a = s.chamar_proximo(INICIO)
                        antes = self.retrato(s)
                        alvos = ((a, 'concluir' if concluir else 'cancelar'),
                                 (a.paciente, 'concluir_atendimento' if concluir else 'cancelar'),
                                 (a.medico, 'concluir_atendimento' if concluir else 'cancelar_atendimento'),
                                 (s._heap_medicos, 'inserir'))
                        objeto, nome = alvos[etapa]
                        original = getattr(objeto, nome)
                        erro = RuntimeError('injetada')

                        def falhar(*args):
                            if depois:
                                original(*args)
                            raise erro

                        operacao = s.concluir_atendimento if concluir else s.cancelar_paciente
                        id = a.id if concluir else a.paciente.id
                        with patch.object(objeto, nome, side_effect=falhar):
                            with self.assertRaises(RuntimeError) as capturado:
                                operacao(id, FIM)
                        self.assertIs(capturado.exception, erro)
                        self.assertEqual(self.retrato(s), antes)
                        self.conferir(s)
                        operacao(id, FIM)
                        self.conferir(s)

    def test_falhas_antes_e_depois_das_mutacoes_na_espera(self):
        for etapa in range(3):
            for depois in (False, True):
                with self.subTest(etapa=etapa, depois=depois):
                    s = self.preparar()
                    p = s.buscar_paciente(4)
                    antes = self.retrato(s)
                    objeto, nome = ((s._heap_pacientes, 'remover'),
                                    (s._arvore_espera, 'remover'), (p, 'cancelar'))[etapa]
                    original = getattr(objeto, nome)
                    chamadas = []
                    erro = RuntimeError('injetada')

                    def falhar(*args):
                        chamadas.append(args)
                        if len(chamadas) == 1:
                            if depois:
                                original(*args)
                            raise erro
                        return original(*args)

                    with patch.object(objeto, nome, side_effect=falhar):
                        with self.assertRaises(RuntimeError):
                            s.cancelar_paciente(p.id, FIM)
                    self.assertEqual(self.retrato(s), antes)
                    self.conferir(s)
                    s.cancelar_paciente(p.id, FIM)
                    self.conferir(s)

    def test_falhas_de_recuperacao_propagadas_e_estados_restaurados(self):
        s = self.preparar()
        a = s.chamar_proximo(INICIO)
        erro, recuperacao = RuntimeError('inserir'), RuntimeError('remover')
        with patch.object(s._heap_medicos, 'inserir', side_effect=erro), patch.object(s._heap_medicos, 'remover', side_effect=recuperacao):
            with self.assertRaises(ExceptionGroup) as capturado:
                s.concluir_atendimento(a.id, FIM)
        self.assertEqual(capturado.exception.exceptions, (erro, recuperacao))
        self.assertEqual(a.medico.total_concluidos, 0)
        self.assertIsNone(a.fim)
        with self.assertRaises(SistemaIndisponivel):
            s.listar_pacientes()
        s = self.preparar()
        paciente = s.buscar_paciente(4)
        with patch.object(s._arvore_espera, 'remover', side_effect=erro), patch.object(s._heap_pacientes, 'inserir', side_effect=recuperacao):
            with self.assertRaises(ExceptionGroup) as capturado:
                s.cancelar_paciente(4, FIM)
        self.assertIn(recuperacao, capturado.exception.exceptions)
        self.assertEqual(paciente.situacao, SituacaoPaciente.AGUARDANDO)
        with self.assertRaises(SistemaIndisponivel):
            s.listar_fila()

    def test_restauracao_de_contador_positivo_e_solicitacao_antiga(self):
        s = SistemaAtendimento()
        s.cadastrar_medico('Médica', 'FICTICIO')
        for i in range(3):
            s.cadastrar_paciente(f'Paciente {i}', INICIO, 1)
        antigo = s.chamar_proximo(INICIO)
        s.concluir_atendimento(antigo.id, FIM)
        atual = s.chamar_proximo(FIM)
        antes = self.retrato(s)
        with self.assertRaises(ValueError):
            s.concluir_atendimento(antigo.id, FIM)
        self.assertEqual(self.retrato(s), antes)
        with self.assertRaises(ValueError):
            s.cancelar_paciente(antigo.paciente.id, FIM)
        self.assertEqual(self.retrato(s), antes)
        inserir = s._heap_medicos.inserir

        def falhar(*args):
            inserir(*args)
            raise RuntimeError('após reinserção')

        with patch.object(s._heap_medicos, 'inserir', side_effect=falhar):
            with self.assertRaises(RuntimeError):
                s.concluir_atendimento(atual.id, FIM)
        self.assertEqual(self.retrato(s), antes)
        self.assertEqual(atual.medico.total_concluidos, 1)
        self.conferir(s)
        s.cancelar_paciente(atual.paciente.id, FIM)
        self.assertEqual(atual.medico.total_concluidos, 1)
        self.assertEqual(atual.medico.ultima_atribuicao, FIM)
        self.conferir(s)

    def test_encerramentos_rejeitam_instantes_anteriores_na_hora_repetida(self):
        fuso = ZoneInfo("America/New_York")
        cedo = datetime(2026, 11, 1, 1, 30, tzinfo=fuso)
        tarde = cedo.replace(fold=1)
        sistema = SistemaAtendimento()
        paciente = sistema.cadastrar_paciente("Ana", tarde, 1)
        sistema.cadastrar_medico("Lia", "FICT-001")

        with self.assertRaisesRegex(ValueError, "anteceder"):
            sistema.cancelar_paciente(paciente.id, cedo)
        self.assertEqual(sistema.listar_fila(), [paciente])
        atendimento = sistema.chamar_proximo(tarde)

        for operacao, id in (
            (sistema.concluir_atendimento, atendimento.id),
            (sistema.cancelar_atendimento, atendimento.id),
            (sistema.cancelar_paciente, paciente.id),
        ):
            with self.subTest(operacao=operacao.__name__):
                with self.assertRaisesRegex(ValueError, "anteceder"):
                    operacao(id, cedo)
                self.assertEqual(sistema.listar_atendimentos_ativos(), [atendimento])
                self.assertIsNone(atendimento.fim)

        sistema.concluir_atendimento(atendimento.id, tarde.astimezone(timezone.utc))
        self.assertEqual(atendimento.medico.total_concluidos, 1)
        sistema.validar_indices()
