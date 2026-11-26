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
        tabela = TabelaHash[object](capacidade=3)
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
        tabela = TabelaHash[object](capacidade=1)
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
