from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from atendimentos.domain.medico import SituacaoMedico
from atendimentos.domain.paciente import SituacaoPaciente
from atendimentos.services.sistema_atendimento import SistemaAtendimento, SistemaIndisponivel


INICIO = datetime(2026, 11, 26, 10, tzinfo=timezone.utc)


class CadastrosTests(TestCase):
    def setUp(self):
        self.sistema = SistemaAtendimento()

    def conferir(self, sistema, pacientes, medicos):
        self.assertCountEqual(sistema.listar_pacientes(), pacientes)
        self.assertCountEqual(sistema.listar_medicos(), medicos)
        self.assertEqual(sistema.listar_fila(), sorted(pacientes, key=lambda p: p.chave_chegada))
        for estrutura in (sistema._pacientes, sistema._arvore_espera, sistema._heap_pacientes,
                          sistema._medicos, sistema._heap_medicos, sistema._atendimentos):
            estrutura.validar()
        self.assertEqual(len(sistema._heap_pacientes), len(pacientes))
        self.assertEqual(len(sistema._heap_medicos), len(medicos))
        for paciente in pacientes:
            self.assertIs(sistema.buscar_paciente(paciente.id), paciente)
            self.assertIs(sistema._arvore_espera.buscar(paciente.chave_chegada), paciente)
            posicao = sistema._heap_pacientes._posicoes.buscar(paciente.id)
            self.assertIs(sistema._heap_pacientes._itens[posicao], paciente)
        for medico in medicos:
            self.assertIs(sistema.buscar_medico(medico.id), medico)
            posicao = sistema._heap_medicos._posicoes.buscar(medico.id)
            self.assertIs(sistema._heap_medicos._itens[posicao], medico)
        self.assertEqual(len(sistema._atendimentos), 0)

    def test_cadastros_validos_estados_e_identidade(self):
        paciente = self.sistema.cadastrar_paciente(" Ana ", INICIO, 3)
        medico = self.sistema.cadastrar_medico(" Lia ", " FICT-001 ")
        self.assertEqual((paciente.id, paciente.nome, paciente.chegada, paciente.prioridade),
                         (1, "Ana", INICIO, 3))
        self.assertEqual(paciente.situacao, SituacaoPaciente.AGUARDANDO)
        self.assertEqual((medico.id, medico.nome, medico.registro), (1, "Lia", "FICT-001"))
        self.assertEqual(medico.situacao, SituacaoMedico.DISPONIVEL)
        self.assertEqual(medico.total_concluidos, 0)
        self.assertIsNone(medico.ultima_atribuicao)
        self.conferir(self.sistema, [paciente], [medico])

    def test_entradas_invalidas_nao_modificam_indices(self):
        paciente = self.sistema.cadastrar_paciente("Ana", INICIO, 3)
        medico = self.sistema.cadastrar_medico("Lia", "FICT-001")
        for nome, chegada, prioridade in (("", INICIO, 3), (None, INICIO, 3),
                                          ("Ana", None, 3), ("Ana", INICIO.replace(tzinfo=None), 3),
                                          ("Ana", INICIO, True), ("Ana", INICIO, 0),
                                          ("Ana", INICIO, 6), ("Ana", INICIO, "1")):
            with self.subTest(nome=nome, chegada=chegada, prioridade=prioridade):
                with self.assertRaises(ValueError):
                    self.sistema.cadastrar_paciente(nome, chegada, prioridade)
                self.conferir(self.sistema, [paciente], [medico])
        for nome, registro in (("", "FICT"), (None, "FICT"), ("Lia", " "), ("Lia", None)):
            with self.subTest(nome=nome, registro=registro):
                with self.assertRaises(ValueError):
                    self.sistema.cadastrar_medico(nome, registro)
                self.conferir(self.sistema, [paciente], [medico])
        self.assertEqual(self.sistema.cadastrar_paciente("Eva", INICIO, 1).id, 10)
        self.assertEqual(self.sistema.cadastrar_medico("Rui", "FICT-002").id, 6)

    def test_consultas_ausentes_e_listagens_vazias(self):
        self.assertIsNone(self.sistema.buscar_paciente(99))
        self.assertIsNone(self.sistema.buscar_medico(99))
        self.conferir(self.sistema, [], [])
        for consulta in (self.sistema.buscar_paciente, self.sistema.buscar_medico):
            for id in (True, "1", None, 1.0):
                with self.subTest(id=id), self.assertRaises(ValueError):
                    consulta(id)

    def test_consultas_delegam_as_hashes_e_fila_a_arvore(self):
        paciente = self.sistema.cadastrar_paciente("Ana", INICIO, 3)
        medico = self.sistema.cadastrar_medico("Lia", "FICT-001")
        for consulta, tabela, registro in ((self.sistema.buscar_paciente, self.sistema._pacientes, paciente),
                                          (self.sistema.buscar_medico, self.sistema._medicos, medico)):
            with patch.object(tabela, "buscar", wraps=tabela.buscar) as buscar:
                self.assertIs(consulta(registro.id), registro)
                buscar.assert_called_once_with(registro.id)
        with patch.object(self.sistema._arvore_espera, "em_ordem", wraps=self.sistema._arvore_espera.em_ordem) as percurso:
            self.assertEqual(self.sistema.listar_fila(), [paciente])
            percurso.assert_called_once_with()

    def test_ordenacao_cronologica_e_clinica_sao_independentes(self):
        p1 = self.sistema.cadastrar_paciente("Ana", INICIO, 5)
        p2 = self.sistema.cadastrar_paciente("Eva", INICIO + timedelta(minutes=1), 1)
        p3 = self.sistema.cadastrar_paciente("Rui", INICIO, 1)
        p4 = self.sistema.cadastrar_paciente("Ivo", INICIO, 1)
        self.assertEqual(self.sistema.listar_fila(), [p1, p3, p4, p2])
        self.conferir(self.sistema, [p1, p2, p3, p4], [])
        for esperado in (p3, p4, p2, p1):
            self.assertIs(self.sistema._heap_pacientes.extrair_minimo(), esperado)

    def test_ids_unicos_com_dados_repetidos_e_redimensionamento(self):
        pacientes = [self.sistema.cadastrar_paciente("Ana", INICIO, i % 5 + 1) for i in range(40)]
        medicos = [self.sistema.cadastrar_medico("Lia", "FICT") for _ in range(40)]
        self.assertEqual([p.id for p in pacientes], list(range(1, 41)))
        self.assertEqual([m.id for m in medicos], list(range(1, 41)))
        self.conferir(self.sistema, pacientes, medicos)
        for medico in medicos:
            self.assertIs(self.sistema._heap_medicos.extrair_minimo(), medico)

    def test_listagens_nao_expoem_recipientes_internos(self):
        paciente = self.sistema.cadastrar_paciente("Ana", INICIO, 3)
        medico = self.sistema.cadastrar_medico("Lia", "FICT")
        for listar, esperado in ((self.sistema.listar_pacientes, paciente),
                                 (self.sistema.listar_fila, paciente),
                                 (self.sistema.listar_medicos, medico)):
            lista = listar()
            self.assertIs(lista[0], esperado)
            lista.clear()
            self.assertIs(listar()[0], esperado)
        self.conferir(self.sistema, [paciente], [medico])

    def test_cadastros_em_instancias_distintas_sao_independentes(self):
        outro = SistemaAtendimento()
        p = self.sistema.cadastrar_paciente("Ana", INICIO, 3)
        m = self.sistema.cadastrar_medico("Lia", "FICT")
        self.conferir(outro, [], [])
        self.assertEqual(outro.cadastrar_paciente("Eva", INICIO, 1).id, 1)
        self.assertEqual(outro.cadastrar_medico("Rui", "FICT").id, 1)
        self.conferir(self.sistema, [p], [m])

    def test_compensa_falhas_antes_e_depois_de_cada_insercao(self):
        for tipo, alvos in (("paciente", ("_pacientes", "_arvore_espera", "_heap_pacientes")),
                            ("medico", ("_medicos", "_heap_medicos"))):
            for alvo in alvos:
                for depois in (False, True):
                    with self.subTest(tipo=tipo, alvo=alvo, depois=depois):
                        sistema = SistemaAtendimento()
                        pacientes = [sistema.cadastrar_paciente("Ana", INICIO, 3) for _ in range(8)]
                        medicos = [sistema.cadastrar_medico("Lia", "FICT") for _ in range(8)]
                        estrutura = getattr(sistema, alvo)
                        inserir = estrutura.inserir
                        erro = RuntimeError("falha injetada")

                        def falhar(*args):
                            if depois:
                                inserir(*args)
                            raise erro

                        with patch.object(estrutura, "inserir", side_effect=falhar):
                            with self.assertRaises(RuntimeError) as capturado:
                                if tipo == "paciente":
                                    sistema.cadastrar_paciente("Eva", INICIO, 1)
                                else:
                                    sistema.cadastrar_medico("Rui", "FICT")
                            self.assertIs(capturado.exception, erro)
                        self.conferir(sistema, pacientes, medicos)
                        if tipo == "paciente":
                            novo = sistema.cadastrar_paciente("Eva", INICIO, 1)
                            pacientes.append(novo)
                        else:
                            novo = sistema.cadastrar_medico("Rui", "FICT")
                            medicos.append(novo)
                        self.assertEqual(novo.id, 10)
                        self.conferir(sistema, pacientes, medicos)

    def test_falha_na_compensacao_e_propagada_e_demais_remocoes_sao_tentadas(self):
        erro = RuntimeError("insercao")
        erro_remocao = RuntimeError("remocao")
        with patch.object(self.sistema._heap_pacientes, "inserir", side_effect=erro), \
             patch.object(self.sistema._arvore_espera, "remover", side_effect=erro_remocao):
            with self.assertRaises(ExceptionGroup) as capturado:
                self.sistema.cadastrar_paciente("Ana", INICIO, 1)
        self.assertEqual(capturado.exception.exceptions[:2], (erro, erro_remocao))
        self.assertIsNone(self.sistema._pacientes.buscar(1))
        with self.assertRaises(SistemaIndisponivel):
            self.sistema.buscar_paciente(1)
        self.assertEqual(len(self.sistema._heap_pacientes), 0)
