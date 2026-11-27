from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from atendimentos.services.sistema_atendimento import SistemaAtendimento


INICIO = datetime(2026, 11, 26, 10, tzinfo=timezone.utc)


class ReclassificacaoTests(TestCase):
    def setUp(self):
        self.sistema = SistemaAtendimento()
        self.pacientes = [self.sistema.cadastrar_paciente(f"Paciente {i}", INICIO, 3)
                          for i in range(7)]

    def conferir(self):
        sistema = self.sistema
        for estrutura in (sistema._pacientes, sistema._arvore_espera, sistema._heap_pacientes):
            estrutura.validar()
            self.assertEqual(len(estrutura), len(self.pacientes))
        self.assertEqual(sistema.listar_fila(), sorted(self.pacientes, key=lambda p: p.chave_chegada))
        self.assertIs(sistema._heap_pacientes.consultar_minimo(),
                      min(self.pacientes, key=lambda p: p.chave_prioridade))
        for paciente in self.pacientes:
            self.assertIs(sistema.buscar_paciente(paciente.id), paciente)
            self.assertIs(sistema._arvore_espera.buscar(paciente.chave_chegada), paciente)
            posicao = sistema._heap_pacientes._posicoes.buscar(paciente.id)
            self.assertIs(sistema._heap_pacientes._itens[posicao], paciente)
            self.assertEqual(sum(item is paciente for item in sistema._heap_pacientes._itens), 1)

    def test_aumento_e_reducao_da_urgencia(self):
        alvo = self.pacientes[-1]
        identidade = (alvo.id, alvo.chegada)
        self.assertIs(self.sistema.reclassificar_paciente(alvo.id, 1), alvo)
        self.assertIs(self.sistema._heap_pacientes.consultar_minimo(), alvo)
        self.conferir()
        self.sistema.reclassificar_paciente(alvo.id, 5)
        self.assertIs(self.sistema._heap_pacientes.consultar_minimo(), self.pacientes[0])
        self.assertEqual((alvo.id, alvo.chegada), identidade)
        self.conferir()

    def test_prioridade_inalterada_preserva_ordem_e_quantidade(self):
        itens = list(self.sistema._heap_pacientes._itens)
        alvo = self.pacientes[3]
        self.assertIs(self.sistema.reclassificar_paciente(alvo.id, 3), alvo)
        self.assertEqual(self.sistema._heap_pacientes._itens, itens)
        self.conferir()

    def test_desempates_por_chegada_e_id(self):
        mais_tarde = self.sistema.cadastrar_paciente("Tardio", INICIO + timedelta(minutes=1), 5)
        self.pacientes.append(mais_tarde)
        for paciente in (mais_tarde, self.pacientes[2], self.pacientes[1]):
            self.sistema.reclassificar_paciente(paciente.id, 1)
        self.conferir()
        for esperado in (self.pacientes[1], self.pacientes[2], mais_tarde):
            self.assertIs(self.sistema._heap_pacientes.extrair_minimo(), esperado)

    def test_reclassificacoes_sucessivas_sem_duplicacao(self):
        for rodada in range(10):
            for paciente in self.pacientes:
                self.sistema.reclassificar_paciente(paciente.id, (paciente.id + rodada) % 5 + 1)
                self.conferir()
        self.assertEqual(self.sistema._ultimo_id_paciente, len(self.pacientes))

    def test_reutiliza_hash_entidade_e_atualizacao_sem_alterar_outros_indices(self):
        sistema = self.sistema
        alvo = self.pacientes[-1]
        raiz = sistema._arvore_espera._raiz
        buckets = sistema._pacientes._buckets
        with ExitStack() as pilha:
            for estrutura in (sistema._pacientes, sistema._arvore_espera, sistema._heap_pacientes):
                for nome in ("inserir", "remover"):
                    pilha.enter_context(patch.object(estrutura, nome, side_effect=AssertionError("operação indevida")))
            buscar = pilha.enter_context(patch.object(sistema._pacientes, "buscar", wraps=sistema._pacientes.buscar))
            entidade = pilha.enter_context(patch.object(alvo, "reclassificar", wraps=alvo.reclassificar))
            atualizar = pilha.enter_context(patch.object(sistema._heap_pacientes, "atualizar", wraps=sistema._heap_pacientes.atualizar))
            sistema.reclassificar_paciente(alvo.id, 1)
            buscar.assert_called_once_with(alvo.id)
            entidade.assert_called_once_with(1)
            atualizar.assert_called_once_with(alvo.id)
        self.assertIs(sistema._arvore_espera._raiz, raiz)
        self.assertIs(sistema._pacientes._buckets, buckets)
        self.conferir()

    def test_prioridades_invalidas_sem_efeitos_colaterais(self):
        alvo = self.pacientes[0]
        itens = list(self.sistema._heap_pacientes._itens)
        for prioridade in (0, 6, -1, True, False, None, "1", 1.5):
            with self.subTest(prioridade=prioridade):
                with patch.object(self.sistema._heap_pacientes, "atualizar") as atualizar:
                    with self.assertRaises(ValueError):
                        self.sistema.reclassificar_paciente(alvo.id, prioridade)
                    atualizar.assert_not_called()
                self.assertEqual(alvo.prioridade, 3)
                self.assertEqual(self.sistema._heap_pacientes._itens, itens)
                self.conferir()

    def test_id_inexistente_ou_invalido(self):
        with self.assertRaises(KeyError) as erro:
            self.sistema.reclassificar_paciente(999, 1)
        self.assertEqual(erro.exception.args, (999,))
        for id in (None, True, "1", 1.0):
            with self.subTest(id=id), self.assertRaises(ValueError):
                self.sistema.reclassificar_paciente(id, 1)
        self.conferir()

    def test_estados_incompativeis_nao_alteram_paciente_nem_heap(self):
        for estado in ("em_atendimento", "concluido", "cancelado"):
            with self.subTest(estado=estado):
                sistema = SistemaAtendimento()
                paciente = sistema.cadastrar_paciente("Ana", INICIO, 3)
                # Preparação isolada do estado; nenhuma operação futura do serviço.
                sistema._heap_pacientes.remover(paciente.id)
                sistema._arvore_espera.remover(paciente.chave_chegada)
                if estado == "cancelado":
                    paciente.cancelar()
                else:
                    paciente.iniciar_atendimento()
                    if estado == "concluido":
                        paciente.concluir_atendimento()
                antes = (paciente.prioridade, paciente.situacao, paciente.id, paciente.chegada)
                with patch.object(sistema._heap_pacientes, "atualizar") as atualizar:
                    with self.assertRaises(ValueError):
                        sistema.reclassificar_paciente(paciente.id, 1)
                    atualizar.assert_not_called()
                self.assertEqual((paciente.prioridade, paciente.situacao, paciente.id, paciente.chegada), antes)
                self.assertEqual(len(sistema._heap_pacientes), 0)
                self.assertEqual(sistema.listar_fila(), [])
                self.assertIs(sistema.buscar_paciente(paciente.id), paciente)

    def test_compensa_falha_antes_ou_depois_de_atualizar_nas_duas_direcoes(self):
        for depois in (False, True):
            for sobe in (False, True):
                with self.subTest(depois=depois, sobe=sobe):
                    self.setUp()
                    alvo = self.pacientes[-1] if sobe else self.pacientes[0]
                    nova = 1 if sobe else 5
                    atualizar = self.sistema._heap_pacientes.atualizar
                    erro = RuntimeError("falha injetada")
                    chamadas = []

                    def falhar_uma_vez(id):
                        chamadas.append(id)
                        if len(chamadas) == 1:
                            if depois:
                                atualizar(id)
                            raise erro
                        atualizar(id)

                    with patch.object(self.sistema._heap_pacientes, "atualizar", side_effect=falhar_uma_vez):
                        with self.assertRaises(RuntimeError) as capturado:
                            self.sistema.reclassificar_paciente(alvo.id, nova)
                    self.assertIs(capturado.exception, erro)
                    self.assertEqual(chamadas, [alvo.id, alvo.id])
                    self.assertEqual(alvo.prioridade, 3)
                    self.conferir()
                    self.sistema.reclassificar_paciente(alvo.id, nova)
                    self.conferir()

    def test_falha_de_recuperacao_e_propagada_explicitamente(self):
        erro = RuntimeError("atualizacao")
        recuperacao = RuntimeError("recuperacao")
        alvo = self.pacientes[-1]
        with patch.object(self.sistema._heap_pacientes, "atualizar", side_effect=[erro, recuperacao]):
            with self.assertRaises(ExceptionGroup) as capturado:
                self.sistema.reclassificar_paciente(alvo.id, 1)
        self.assertEqual(capturado.exception.exceptions, (erro, recuperacao))
        self.assertEqual(alvo.prioridade, 3)
