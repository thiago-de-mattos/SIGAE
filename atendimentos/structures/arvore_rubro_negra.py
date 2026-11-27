"""Árvore Rubro-Negra própria para o índice cronológico de pacientes."""

from datetime import datetime

from atendimentos.contratos import ChaveChegada
from atendimentos.domain.paciente import Paciente


class _No:
    def __init__(self, chave=None, paciente=None, cor="preto"):
        self.chave = chave
        self.paciente = paciente
        self.cor = cor
        self.pai = self
        self.esquerda = self
        self.direita = self


class ArvoreRubroNegra:
    """ContratoArvore, sem cópias de pacientes ou índices auxiliares prontos.

    Busca/inserção/remoção: O(log(n+1)) no pior caso, comparações O(1).
    Rotação: O(1). len: O(1). em_ordem e validar: O(n) no pior caso.
    Espaço permanente O(n); percurso O(n) para o resultado e O(log(n+1))
    de pilha; validação O(log(n+1)) auxiliar para uma árvore válida (O(n)
    em organização inválida). Não depende de amortização ou dispersão.
    A elegibilidade dos pacientes pertence ao serviço, não à estrutura.
    """

    def __init__(self):
        self._nil = _No()
        self._raiz = self._nil
        self._quantidade = 0

    def __len__(self) -> int:
        return self._quantidade

    @staticmethod
    def _validar_chave(chave):
        if (not isinstance(chave, tuple) or len(chave) != 2
                or not isinstance(chave[0], datetime)
                or chave[0].utcoffset() is None
                or type(chave[1]) is not int or chave[1] <= 0):
            raise ValueError("A chave deve ser (chegada com fuso, ID positivo).")

    def _buscar_no(self, chave):
        self._validar_chave(chave)
        no = self._raiz
        while no is not self._nil:
            if chave == no.chave:
                return no
            no = no.esquerda if chave < no.chave else no.direita
        return self._nil

    def buscar(self, chave: ChaveChegada) -> Paciente | None:
        return self._buscar_no(chave).paciente

    def _rotacionar_esquerda(self, no):
        filho = no.direita
        no.direita = filho.esquerda
        if filho.esquerda is not self._nil:
            filho.esquerda.pai = no
        filho.pai = no.pai
        if no.pai is self._nil:
            self._raiz = filho
        elif no is no.pai.esquerda:
            no.pai.esquerda = filho
        else:
            no.pai.direita = filho
        filho.esquerda = no
        no.pai = filho

    def _rotacionar_direita(self, no):
        filho = no.esquerda
        no.esquerda = filho.direita
        if filho.direita is not self._nil:
            filho.direita.pai = no
        filho.pai = no.pai
        if no.pai is self._nil:
            self._raiz = filho
        elif no is no.pai.direita:
            no.pai.direita = filho
        else:
            no.pai.esquerda = filho
        filho.direita = no
        no.pai = filho

    def inserir(self, chave: ChaveChegada, paciente: Paciente) -> None:
        self._validar_chave(chave)
        if not isinstance(paciente, Paciente) or chave != paciente.chave_chegada:
            raise ValueError("Chave divergente do paciente.")
        pai = self._nil
        atual = self._raiz
        while atual is not self._nil:
            pai = atual
            if chave == atual.chave:
                raise ValueError("Chave duplicada.")
            atual = atual.esquerda if chave < atual.chave else atual.direita
        no = _No(chave, paciente, "vermelho")
        no.pai, no.esquerda, no.direita = pai, self._nil, self._nil
        if pai is self._nil:
            self._raiz = no
        elif chave < pai.chave:
            pai.esquerda = no
        else:
            pai.direita = no
        self._quantidade += 1
        self._corrigir_insercao(no)

    def _corrigir_insercao(self, no):
        while no.pai.cor == "vermelho":
            if no.pai is no.pai.pai.esquerda:
                tio = no.pai.pai.direita
                if tio.cor == "vermelho":
                    no.pai.cor = tio.cor = "preto"
                    no.pai.pai.cor = "vermelho"
                    no = no.pai.pai
                else:
                    if no is no.pai.direita:
                        no = no.pai
                        self._rotacionar_esquerda(no)
                    no.pai.cor = "preto"
                    no.pai.pai.cor = "vermelho"
                    self._rotacionar_direita(no.pai.pai)
            else:
                tio = no.pai.pai.esquerda
                if tio.cor == "vermelho":
                    no.pai.cor = tio.cor = "preto"
                    no.pai.pai.cor = "vermelho"
                    no = no.pai.pai
                else:
                    if no is no.pai.esquerda:
                        no = no.pai
                        self._rotacionar_direita(no)
                    no.pai.cor = "preto"
                    no.pai.pai.cor = "vermelho"
                    self._rotacionar_esquerda(no.pai.pai)
        self._raiz.cor = "preto"

    def _transplantar(self, antigo, novo):
        if antigo.pai is self._nil:
            self._raiz = novo
        elif antigo is antigo.pai.esquerda:
            antigo.pai.esquerda = novo
        else:
            antigo.pai.direita = novo
        # NIL guarda temporariamente o pai necessário para corrigir a remoção.
        novo.pai = antigo.pai

    def remover(self, chave: ChaveChegada) -> Paciente:
        no = self._buscar_no(chave)
        if no is self._nil:
            raise KeyError(chave)
        sucessor = no
        cor_original = sucessor.cor
        if no.esquerda is self._nil:
            substituto = no.direita
            self._transplantar(no, no.direita)
        elif no.direita is self._nil:
            substituto = no.esquerda
            self._transplantar(no, no.esquerda)
        else:
            sucessor = no.direita
            while sucessor.esquerda is not self._nil:
                sucessor = sucessor.esquerda
            cor_original = sucessor.cor
            substituto = sucessor.direita
            if sucessor.pai is no:
                substituto.pai = sucessor
            else:
                self._transplantar(sucessor, sucessor.direita)
                sucessor.direita = no.direita
                sucessor.direita.pai = sucessor
            self._transplantar(no, sucessor)
            sucessor.esquerda = no.esquerda
            sucessor.esquerda.pai = sucessor
            sucessor.cor = no.cor
        self._quantidade -= 1
        if cor_original == "preto":
            self._corrigir_remocao(substituto)
        self._nil.pai = self._nil
        return no.paciente

    def _corrigir_remocao(self, no):
        while no is not self._raiz and no.cor == "preto":
            if no is no.pai.esquerda:
                irmao = no.pai.direita
                if irmao.cor == "vermelho":
                    irmao.cor = "preto"
                    no.pai.cor = "vermelho"
                    self._rotacionar_esquerda(no.pai)
                    irmao = no.pai.direita
                if irmao.esquerda.cor == irmao.direita.cor == "preto":
                    irmao.cor = "vermelho"
                    no = no.pai
                else:
                    if irmao.direita.cor == "preto":
                        irmao.esquerda.cor = "preto"
                        irmao.cor = "vermelho"
                        self._rotacionar_direita(irmao)
                        irmao = no.pai.direita
                    irmao.cor = no.pai.cor
                    no.pai.cor = irmao.direita.cor = "preto"
                    self._rotacionar_esquerda(no.pai)
                    no = self._raiz
            else:
                irmao = no.pai.esquerda
                if irmao.cor == "vermelho":
                    irmao.cor = "preto"
                    no.pai.cor = "vermelho"
                    self._rotacionar_direita(no.pai)
                    irmao = no.pai.esquerda
                if irmao.direita.cor == irmao.esquerda.cor == "preto":
                    irmao.cor = "vermelho"
                    no = no.pai
                else:
                    if irmao.esquerda.cor == "preto":
                        irmao.direita.cor = "preto"
                        irmao.cor = "vermelho"
                        self._rotacionar_esquerda(irmao)
                        irmao = no.pai.esquerda
                    irmao.cor = no.pai.cor
                    no.pai.cor = irmao.esquerda.cor = "preto"
                    self._rotacionar_direita(no.pai)
                    no = self._raiz
        no.cor = "preto"

    def em_ordem(self) -> list[Paciente]:
        resultado, pilha = [], []
        no = self._raiz
        while pilha or no is not self._nil:
            while no is not self._nil:
                pilha.append(no)
                no = no.esquerda
            no = pilha.pop()
            resultado.append(no.paciente)
            no = no.direita
        return resultado

    def validar(self) -> None:
        nil = self._nil
        if (not isinstance(nil, _No) or nil.cor != "preto"
                or nil.paciente is not None or nil.chave is not None
                or nil.esquerda is not nil or nil.direita is not nil or nil.pai is not nil):
            raise ValueError("Sentinela NIL inválida.")
        if type(self._quantidade) is not int or self._quantidade < 0:
            raise ValueError("Quantidade inválida.")
        if (not isinstance(self._raiz, _No) or self._raiz.pai is not nil
                or self._raiz.cor != "preto"):
            raise ValueError("Raiz inválida.")
        pilha = [(self._raiz, nil, None, None, 0)]
        quantidade, altura_negra = 0, None
        while pilha:
            no, pai, inferior, superior, pretos = pilha.pop()
            if no is nil:
                if altura_negra is None:
                    altura_negra = pretos
                elif altura_negra != pretos:
                    raise ValueError("Alturas negras divergentes.")
                continue
            if not isinstance(no, _No) or no.pai is not pai:
                raise ValueError("Referência parental inválida.")
            self._validar_chave(no.chave)
            if ((inferior is not None and not inferior < no.chave)
                    or (superior is not None and not no.chave < superior)):
                raise ValueError("Ordenação BST inválida ou chave duplicada.")
            if not isinstance(no.paciente, Paciente) or no.chave != no.paciente.chave_chegada:
                raise ValueError("Referência ao paciente divergente.")
            if no.cor not in ("preto", "vermelho"):
                raise ValueError("Cor inválida.")
            if not isinstance(no.esquerda, _No) or not isinstance(no.direita, _No):
                raise ValueError("Filhos inválidos.")
            if no.cor == "vermelho" and (no.esquerda.cor != "preto" or no.direita.cor != "preto"):
                raise ValueError("Nó vermelho com filho vermelho.")
            quantidade += 1
            if quantidade > self._quantidade:
                raise ValueError("Quantidade divergente ou referência repetida.")
            pretos += no.cor == "preto"
            pilha.append((no.direita, no, no.chave, superior, pretos))
            pilha.append((no.esquerda, no, inferior, no.chave, pretos))
        if quantidade != self._quantidade:
            raise ValueError("Quantidade divergente.")
