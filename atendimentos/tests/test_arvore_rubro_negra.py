from datetime import datetime, timedelta, timezone
from random import Random
from unittest import TestCase
from unittest.mock import patch

from atendimentos.domain.paciente import Paciente
from atendimentos.structures.arvore_rubro_negra import ArvoreRubroNegra


CHEGADA = datetime(2026, 11, 26, tzinfo=timezone.utc)


class ArvoreRubroNegraTests(TestCase):
    def paciente(self, id, minutos=0):
        return Paciente(id, f"Paciente {id}", CHEGADA + timedelta(minutes=minutos), 3)

    def montar(self, ids):
        arvore = ArvoreRubroNegra()
        for id in ids:
            paciente = self.paciente(id)
            self.assertIsNone(arvore.inserir(paciente.chave_chegada, paciente))
            self.assertIsNone(arvore.validar())
        return arvore

    def conferir(self, arvore, pacientes):
        self.assertIsNone(arvore.validar())
        self.assertEqual(len(arvore), len(pacientes))
        esperado = sorted(pacientes, key=lambda p: p.chave_chegada)
        obtido = arvore.em_ordem()
        self.assertEqual(len(obtido), len(esperado))
        for atual, original in zip(obtido, esperado):
            self.assertIs(atual, original)
            self.assertIs(arvore.buscar(original.chave_chegada), original)

    def test_vazia_e_chave_ausente(self):
        arvore = self.montar([])
        chave = (CHEGADA, 1)
        self.assertIsNone(arvore.buscar(chave))
        self.assertEqual(arvore.em_ordem(), [])
        with self.assertRaises(KeyError) as erro:
            arvore.remover(chave)
        self.assertEqual(erro.exception.args, (chave,))
        self.conferir(arvore, [])

    def test_ordem_cronologica_desempate_e_referencias(self):
        arvore = ArvoreRubroNegra()
        pacientes = [self.paciente(3), self.paciente(2, -1), self.paciente(1)]
        for paciente in pacientes:
            arvore.inserir(paciente.chave_chegada, paciente)
        self.assertEqual([p.id for p in arvore.em_ordem()], [2, 1, 3])
        pacientes[0].reclassificar(1)
        self.conferir(arvore, pacientes)
        listagem = arvore.em_ordem()
        listagem.clear()
        self.conferir(arvore, pacientes)

    def test_duplicada_divergente_e_entradas_invalidas(self):
        arvore = self.montar([1])
        original = arvore.buscar((CHEGADA, 1))
        for paciente in (original, self.paciente(1)):
            with self.assertRaises(ValueError):
                arvore.inserir(paciente.chave_chegada, paciente)
        with self.assertRaises(ValueError):
            arvore.inserir((CHEGADA, 2), original)
        for chave in (None, (CHEGADA,), (CHEGADA, True), (CHEGADA, 0),
                      (datetime(2026, 1, 1), 1), ("hoje", 1)):
            with self.subTest(chave=chave):
                for operacao in (arvore.buscar, arvore.remover):
                    with self.assertRaises(ValueError):
                        operacao(chave)
                with self.assertRaises(ValueError):
                    arvore.inserir(chave, original)
        self.conferir(arvore, [original])

    def test_rotacoes_simples_e_duplas(self):
        for ids, esquerda, direita in (([1, 2, 3], 1, 0), ([3, 2, 1], 0, 1),
                                       ([3, 1, 2], 1, 1), ([1, 3, 2], 1, 1)):
            with self.subTest(ids=ids):
                arvore = ArvoreRubroNegra()
                with patch.object(arvore, '_rotacionar_esquerda', wraps=arvore._rotacionar_esquerda) as re, \
                     patch.object(arvore, '_rotacionar_direita', wraps=arvore._rotacionar_direita) as rd:
                    for id in ids:
                        p = self.paciente(id)
                        arvore.inserir(p.chave_chegada, p)
                        arvore.validar()
                    self.assertEqual(re.call_count, esquerda)
                    self.assertEqual(rd.call_count, direita)
                self.assertEqual(arvore._raiz.paciente.id, 2)

    def test_recoloracao_com_tio_vermelho(self):
        arvore = self.montar([4, 2, 6, 1])
        self.assertEqual(arvore._raiz.cor, 'preto')
        self.assertEqual(arvore._raiz.esquerda.cor, 'preto')
        self.assertEqual(arvore._raiz.direita.cor, 'preto')
        self.assertEqual(arvore._raiz.esquerda.esquerda.cor, 'vermelho')

    def test_remove_zero_um_dois_filhos_e_raiz(self):
        for ids, alvo, filhos in (([2], 2, 0), ([2, 1], 2, 1),
                                  ([2, 1, 3], 2, 2), ([4, 2, 6, 5, 7], 4, 2),
                                  ([2, 1, 3], 1, 0)):
            with self.subTest(ids=ids, alvo=alvo):
                arvore = self.montar(ids)
                no = arvore._buscar_no((CHEGADA, alvo))
                self.assertEqual(sum(f is not arvore._nil for f in (no.esquerda, no.direita)), filhos)
                esperado = [p for p in arvore.em_ordem() if p.id != alvo]
                self.assertIs(arvore.remover(no.chave), no.paciente)
                self.assertIsNone(arvore.buscar((CHEGADA, alvo)))
                with self.assertRaises(KeyError):
                    arvore.remover((CHEGADA, alvo))
                self.conferir(arvore, esperado)

    def test_remove_raizes_ate_esvaziar_e_reinsere(self):
        arvore = self.montar(range(1, 60))
        while len(arvore):
            paciente = arvore._raiz.paciente
            self.assertIs(arvore.remover(paciente.chave_chegada), paciente)
            arvore.validar()
        self.assertIs(arvore._raiz, arvore._nil)
        p = self.paciente(1)
        arvore.inserir(p.chave_chegada, p)
        self.conferir(arvore, [p])

    def test_sequencias_ordenadas_inversas_e_embaralhadas(self):
        for semente in range(10):
            rng = Random(semente)
            ids = list(range(1, 81))
            if semente == 1:
                ids.reverse()
            elif semente > 1:
                rng.shuffle(ids)
            arvore = ArvoreRubroNegra()
            ativos = []
            for id in ids:
                p = self.paciente(id)
                ativos.append(p)
                arvore.inserir(p.chave_chegada, p)
                self.conferir(arvore, ativos)
            rng.shuffle(ativos)
            while ativos:
                p = ativos.pop()
                self.assertIs(arvore.remover(p.chave_chegada), p)
                self.conferir(arvore, ativos)

    def test_validar_detecta_inconsistencias(self):
        for caso in ('nil', 'raiz', 'cor', 'pai', 'bst', 'quantidade', 'altura', 'vermelho', 'paciente', 'ciclo'):
            with self.subTest(caso=caso):
                arvore = self.montar([4, 2, 6, 1])
                raiz = arvore._raiz
                if caso == 'nil':
                    arvore._nil.cor = 'vermelho'
                elif caso == 'raiz':
                    raiz.cor = 'vermelho'
                elif caso == 'cor':
                    raiz.esquerda.cor = 'azul'
                elif caso == 'pai':
                    raiz.esquerda.pai = arvore._nil
                elif caso == 'bst':
                    raiz.esquerda.chave = raiz.chave
                elif caso == 'quantidade':
                    arvore._quantidade += 1
                elif caso == 'altura':
                    raiz.direita.cor = 'vermelho'
                elif caso == 'vermelho':
                    raiz.esquerda.cor = 'vermelho'
                elif caso == 'paciente':
                    raiz.paciente = self.paciente(99)
                else:
                    raiz.esquerda = raiz
                with self.assertRaises(ValueError):
                    arvore.validar()

    def test_instancias_independentes(self):
        primeira = self.montar([1, 2])
        segunda = self.montar([1])
        self.assertIsNot(primeira._nil, segunda._nil)
        primeira.remover((CHEGADA, 1))
        self.assertEqual(len(segunda), 1)
        segunda.validar()
