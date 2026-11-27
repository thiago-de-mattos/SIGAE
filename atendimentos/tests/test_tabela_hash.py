from datetime import datetime, timezone
from unittest import TestCase

from atendimentos.domain.paciente import Paciente
from atendimentos.structures.tabela_hash import TabelaHash


class TabelaHashTests(TestCase):
    def test_inicia_vazia_com_capacidade_padrao(self):
        tabela = TabelaHash()
        self.assertEqual(tabela._capacidade, 11)
        self.assertEqual(tabela._fator_carga_maximo, 0.75)
        self.assertEqual(len(tabela), 0)
        self.assertIsNone(tabela.buscar(1))

    def test_rejeita_capacidades_invalidas(self):
        for capacidade in (0, -1, True, 1.5, "11", None):
            with self.subTest(capacidade=capacidade):
                with self.assertRaises(ValueError):
                    TabelaHash(capacidade=capacidade)

    def test_configura_e_valida_fator_de_carga(self):
        self.assertEqual(TabelaHash(3, 1.5)._fator_carga_maximo, 1.5)
        for fator in (0, -1, True, "0.75", None, float("nan"), float("inf")):
            with self.subTest(fator=fator):
                with self.assertRaises(ValueError):
                    TabelaHash(fator_carga_maximo=fator)

    def test_insere_e_consulta_preservando_referencia(self):
        tabela = TabelaHash[Paciente]()
        paciente = Paciente(1, "Ana", datetime.now(timezone.utc), 3)
        self.assertIsNone(tabela.inserir(paciente.id, paciente))
        self.assertEqual(len(tabela), 1)
        self.assertIs(tabela.buscar(1), paciente)
        paciente.reclassificar(1)
        self.assertEqual(tabela.buscar(1).prioridade, 1)

    def test_colisoes_usam_modulo_e_encadeamento_separado(self):
        tabela = TabelaHash[object](capacidade=3, fator_carga_maximo=2)
        valores = [object(), object(), object()]
        for chave, valor in zip((1, 4, 7), valores):
            tabela.inserir(chave, valor)
        self.assertEqual(len(tabela), 3)
        self.assertEqual([len(bucket) for bucket in tabela._buckets], [0, 3, 0])
        for chave, valor in zip((1, 4, 7), valores):
            self.assertIs(tabela.buscar(chave), valor)
        self.assertIsNone(tabela.buscar(10))
        self.assertIsNone(tabela.buscar(2))

    def test_chaves_repetidas_nao_substituem_nem_alteram_quantidade(self):
        tabela = TabelaHash[object](capacidade=1, fator_carga_maximo=4)
        valores = [object(), object(), object()]
        for chave, valor in enumerate(valores, start=1):
            tabela.inserir(chave, valor)
        for chave, valor in enumerate(valores, start=1):
            with self.subTest(chave=chave):
                with self.assertRaises(ValueError):
                    tabela.inserir(chave, object())
                self.assertEqual(len(tabela), 3)
                self.assertIs(tabela.buscar(chave), valor)

    def test_rejeita_none_sem_alterar_tabela(self):
        tabela = TabelaHash[int]()
        tabela.inserir(1, 0)
        for chave in (1, 12):
            with self.subTest(chave=chave):
                with self.assertRaises(ValueError):
                    tabela.inserir(chave, None)
        self.assertEqual(len(tabela), 1)
        self.assertEqual(tabela.buscar(1), 0)
        self.assertIsNone(tabela.buscar(12))

    def test_rejeita_chaves_nao_inteiras_sem_alterar_tabela(self):
        tabela = TabelaHash[str]()
        tabela.inserir(1, "original")
        for chave in (True, False, 1.0, "1", None, []):
            with self.subTest(chave=chave):
                with self.assertRaises(ValueError):
                    tabela.inserir(chave, "novo")
                with self.assertRaises(ValueError):
                    tabela.buscar(chave)
        self.assertEqual(len(tabela), 1)
        self.assertEqual(tabela.buscar(1), "original")

    def test_valores_genericos_incluindo_falsos(self):
        tabela = TabelaHash[object]()
        valores = [0, False, "", []]
        for chave, valor in enumerate(valores):
            tabela.inserir(chave, valor)
            self.assertIs(tabela.buscar(chave), valor)
        self.assertEqual(len(tabela), len(valores))

    def test_instancias_nao_compartilham_buckets(self):
        primeira = TabelaHash[str]()
        segunda = TabelaHash[str]()
        primeira.inserir(1, "Ana")
        self.assertIsNone(segunda.buscar(1))
        self.assertEqual(len(segunda), 0)

    def test_remove_inicio_meio_e_fim_de_bucket_com_colisoes(self):
        for removida in (1, 12, 23):
            with self.subTest(removida=removida):
                tabela = TabelaHash[object]()
                registros = [(chave, object()) for chave in (1, 12, 23)]
                for chave, valor in registros:
                    tabela.inserir(chave, valor)
                for chave, valor in registros:
                    if chave == removida:
                        self.assertIs(tabela.remover(chave), valor)
                self.assertEqual(len(tabela), 2)
                self.assertIsNone(tabela.validar())
                self.assertIsNone(tabela.buscar(removida))
                for chave, valor in registros:
                    if chave != removida:
                        self.assertIs(tabela.buscar(chave), valor)

    def test_remove_todos_e_reinsere_chave(self):
        tabela = TabelaHash[int]()
        tabela.inserir(1, 0)
        self.assertEqual(tabela.remover(1), 0)
        self.assertEqual(len(tabela), 0)
        self.assertEqual(tabela.listar_valores(), [])
        with self.assertRaises(KeyError):
            tabela.remover(1)
        tabela.inserir(1, 10)
        self.assertEqual(tabela.buscar(1), 10)
        self.assertEqual(len(tabela), 1)

    def test_remocao_e_atualizacao_ausentes_preservam_registros(self):
        tabela = TabelaHash[object]()
        original = object()
        tabela.inserir(1, original)
        for chave in (12, 2):
            with self.subTest(chave=chave):
                with self.assertRaises(KeyError) as erro:
                    tabela.remover(chave)
                self.assertEqual(erro.exception.args, (chave,))
                with self.assertRaises(KeyError):
                    tabela.atualizar(chave, object())
        self.assertEqual(len(tabela), 1)
        self.assertIs(tabela.buscar(1), original)

    def test_atualiza_referencia_em_bucket_com_colisoes(self):
        tabela = TabelaHash[object]()
        registros = [(chave, object()) for chave in (1, 12, 23)]
        for chave, valor in registros:
            tabela.inserir(chave, valor)
        novo = []
        self.assertIsNone(tabela.atualizar(12, novo))
        self.assertIs(tabela.buscar(12), novo)
        self.assertIs(tabela.buscar(1), registros[0][1])
        self.assertIs(tabela.buscar(23), registros[2][1])
        self.assertEqual(len(tabela), 3)
        self.assertEqual(tabela._capacidade, 11)

    def test_novas_operacoes_rejeitam_entradas_invalidas(self):
        tabela = TabelaHash[int]()
        tabela.inserir(1, 0)
        for chave in (True, 1.0, "1", None, []):
            with self.subTest(chave=chave):
                with self.assertRaises(ValueError):
                    tabela.remover(chave)
                with self.assertRaises(ValueError):
                    tabela.atualizar(chave, 2)
        with self.assertRaises(ValueError):
            tabela.atualizar(1, None)
        self.assertEqual(tabela.buscar(1), 0)
        self.assertEqual(len(tabela), 1)

    def test_listagem_independente_com_referencias_compartilhadas(self):
        tabela = TabelaHash[list[int]]()
        self.assertEqual(tabela.listar_valores(), [])
        valores = [[1], [2], [3]]
        for chave, valor in zip((1, 12, 2), valores):
            tabela.inserir(chave, valor)
        listagem = tabela.listar_valores()
        self.assertEqual(len(listagem), 3)
        for valor in valores:
            self.assertTrue(any(item is valor for item in listagem))
        listagem[0].append(10)
        self.assertTrue(any(10 in valor for valor in tabela.listar_valores()))
        listagem.clear()
        self.assertEqual(len(tabela), 3)
        self.assertEqual(len(tabela.listar_valores()), 3)

    def test_redimensiona_somente_ao_ultrapassar_limite(self):
        tabela = TabelaHash[object](capacidade=4)
        for chave in (1, 5, 9):
            tabela.inserir(chave, object())
        self.assertEqual(tabela._capacidade, 4)
        with self.assertRaises(ValueError):
            tabela.inserir(1, object())
        with self.assertRaises(ValueError):
            tabela.inserir(13, None)
        tabela.atualizar(1, object())
        self.assertEqual(tabela._capacidade, 4)
        tabela.inserir(13, object())
        self.assertEqual(tabela._capacidade, 8)
        self.assertEqual(len(tabela), 4)

    def test_fator_configurado_pode_exigir_varias_duplicacoes(self):
        tabela = TabelaHash[str](capacidade=1, fator_carga_maximo=0.1)
        tabela.inserir(1, "Ana")
        self.assertEqual(tabela._capacidade, 16)
        self.assertLessEqual(len(tabela) / tabela._capacidade, 0.1)
        self.assertEqual(tabela.buscar(1), "Ana")

    def test_multiplos_redimensionamentos_preservam_registros_e_identidade(self):
        tabela = TabelaHash[object]()
        registros = [(chave * 11, object()) for chave in range(100)]
        capacidades = [tabela._capacidade]
        for quantidade, (chave, valor) in enumerate(registros, start=1):
            tabela.inserir(chave, valor)
            self.assertEqual(len(tabela), quantidade)
            self.assertIsNone(tabela.validar())
            self.assertLessEqual(quantidade / tabela._capacidade, 0.75)
            if tabela._capacidade != capacidades[-1]:
                capacidades.append(tabela._capacidade)
            for anterior, referencia in registros[:quantidade]:
                self.assertIs(tabela.buscar(anterior), referencia)
        self.assertGreater(len(capacidades), 2)
        self.assertEqual(len(tabela.listar_valores()), 100)
        for indice, bucket in enumerate(tabela._buckets):
            for chave, _ in bucket:
                self.assertEqual(chave % tabela._capacidade, indice)
        capacidade = tabela._capacidade
        for chave, valor in registros[::2]:
            self.assertIs(tabela.remover(chave), valor)
        self.assertEqual(len(tabela), 50)
        self.assertEqual(tabela._capacidade, capacidade)
        for chave, valor in registros[1::2]:
            self.assertIs(tabela.buscar(chave), valor)
        self.assertIsNone(tabela.validar())

    def test_validar_preserva_organizacao_e_referencias(self):
        tabela = TabelaHash[object](capacidade=4, fator_carga_maximo=1)
        self.assertIsNone(tabela.validar())
        valor = []
        for chave in (9, 1, -3, 0):
            tabela.inserir(chave, valor)
        buckets = tabela._buckets
        referencias = list(buckets)
        registros = [list(bucket) for bucket in buckets]
        self.assertIsNone(tabela.validar())
        self.assertIs(tabela._buckets, buckets)
        for indice, bucket in enumerate(buckets):
            self.assertIs(bucket, referencias[indice])
            for atual, anterior in zip(bucket, registros[indice]):
                self.assertIs(atual, anterior)
        tabela.atualizar(1, valor)
        self.assertIsNone(tabela.validar())
        for chave in (9, 1, -3, 0):
            self.assertIs(tabela.remover(chave), valor)
            self.assertIsNone(tabela.validar())

    def test_validar_detecta_metadados_invalidos(self):
        casos = (
            ("_capacidade", (0, -1, True, 1.5, None, 12)),
            ("_quantidade", (-1, True, 1.0, None, 1)),
            ("_fator_carga_maximo", (0, -1, True, "0.75", None,
                                      float("nan"), float("inf"))),
        )
        for atributo, valores in casos:
            for valor in valores:
                with self.subTest(atributo=atributo, valor=valor):
                    tabela = TabelaHash()
                    setattr(tabela, atributo, valor)
                    with self.assertRaises(ValueError):
                        tabela.validar()

    def test_validar_detecta_organizacao_invalida(self):
        for buckets in (None, (), [], [[]] * 11, [()] + [[] for _ in range(10)]):
            with self.subTest(buckets=buckets):
                tabela = TabelaHash()
                tabela._buckets = buckets
                with self.assertRaises(ValueError):
                    tabela.validar()

    def test_validar_detecta_registros_invalidos(self):
        for registro in (None, (), (1,), (1, 2, 3), [1, 2],
                         (True, 2), (1.0, 2), ("1", 2), (1, None)):
            with self.subTest(registro=registro):
                tabela = TabelaHash()
                tabela._buckets[1].append(registro)
                tabela._quantidade = 1
                with self.assertRaises(ValueError):
                    tabela.validar()

    def test_validar_detecta_bucket_incorreto(self):
        tabela = TabelaHash()
        tabela.inserir(1, object())
        tabela._buckets[2].append(tabela._buckets[1].pop())
        with self.assertRaisesRegex(ValueError, "bucket incorreto"):
            tabela.validar()

    def test_validar_detecta_duplicacao_com_contagem_coerente(self):
        tabela = TabelaHash()
        tabela.inserir(1, object())
        tabela._buckets[1].append((1, object()))
        tabela._quantidade = 2
        with self.assertRaisesRegex(ValueError, "duplicada"):
            tabela.validar()

    def test_validar_detecta_contagem_divergente(self):
        for quantidade in (0, 2):
            with self.subTest(quantidade=quantidade):
                tabela = TabelaHash()
                tabela.inserir(1, object())
                tabela._quantidade = quantidade
                with self.assertRaisesRegex(ValueError, "diverge"):
                    tabela.validar()

    def test_validar_detecta_carga_excedida(self):
        tabela = TabelaHash(capacidade=4)
        for chave in range(3):
            tabela.inserir(chave, object())
        self.assertIsNone(tabela.validar())
        tabela._buckets[3].append((3, object()))
        tabela._quantidade = 4
        with self.assertRaisesRegex(ValueError, "excedido"):
            tabela.validar()
