"""Min-Heap binário com índice próprio de posições por ID."""

from collections.abc import Callable
from typing import Generic, TypeVar

from atendimentos.contratos import Identificavel
from .tabela_hash import TabelaHash


Registro = TypeVar("Registro", bound=Identificavel)


class MinHeap(Generic[Registro]):
    """Recebe chave determinística, sem efeitos colaterais, com tuplas comparáveis.

    IDs devem permanecer imutáveis. Após mudar a chave de um item, chamar
    atualizar(id) antes de outra operação. Elegibilidade e estados pertencem
    ao serviço; este Heap armazena as referências recebidas.

    Para n itens e m buckets da Hash, assumindo comparação O(1): mínimo e len
    O(1); inserir O(log(n+1)) esperado amortizado; remover/extrair/atualizar
    O(log(n+1)) esperado (amortizado para remoções, pela realocação da lista).
    São O(log(n+1)) trocas, cada uma com duas atualizações
    na Hash: pior caso O(n log(n+1)), mais O(m + m_novo + n) em um rehash na
    inserção. Realocações da lista custam O(n), amortizadas nas inserções/remoções.
    validar: limite esperado O(m log(m+1) + n log(n+1)), pior caso
    O(m log(m+1) + n²), incluindo validar e consultas da Hash.
    Espaço O(n+m); validar usa O(n+m) auxiliar. m não diminui após remoções.
    """

    def __init__(self, chave: Callable[[Registro], tuple]) -> None:
        if not callable(chave):
            raise ValueError("A chave deve ser uma função.")
        self._chave = chave
        self._itens: list[Registro] = []
        self._posicoes = TabelaHash[int]()

    def __len__(self) -> int:
        return len(self._itens)

    def consultar_minimo(self) -> Registro | None:
        return self._itens[0] if self._itens else None

    def listar_itens(self) -> list[Registro]:
        """Copia as referências do Heap para conferência dos índices."""
        return self._itens.copy()

    def _trocar(self, a: int, b: int) -> None:
        self._itens[a], self._itens[b] = self._itens[b], self._itens[a]
        self._posicoes.atualizar(self._itens[a].id, a)
        self._posicoes.atualizar(self._itens[b].id, b)

    def _subir(self, posicao: int) -> None:
        while posicao > 0:
            pai = (posicao - 1) // 2
            if not self._chave(self._itens[posicao]) < self._chave(self._itens[pai]):
                break
            self._trocar(posicao, pai)
            posicao = pai

    def _descer(self, posicao: int) -> None:
        while 2 * posicao + 1 < len(self._itens):
            menor = 2 * posicao + 1
            direita = menor + 1
            if direita < len(self._itens) and (
                self._chave(self._itens[direita]) < self._chave(self._itens[menor])
            ):
                menor = direita
            if not self._chave(self._itens[menor]) < self._chave(self._itens[posicao]):
                break
            self._trocar(posicao, menor)
            posicao = menor

    def _reordenar(self, posicao: int) -> None:
        if posicao > 0 and (
            self._chave(self._itens[posicao])
            < self._chave(self._itens[(posicao - 1) // 2])
        ):
            self._subir(posicao)
        else:
            self._descer(posicao)

    def inserir(self, item: Registro) -> None:
        if type(getattr(item, "id", None)) is not int:
            raise ValueError("O item deve possuir ID inteiro.")
        if self._posicoes.buscar(item.id) is not None:
            raise ValueError("ID já presente no Heap.")
        # Valida a chave antes de modificar o armazenamento.
        chave = self._chave(item)
        if not isinstance(chave, tuple):
            raise ValueError("A chave deve produzir uma tupla comparável.")
        posicao = len(self._itens)
        # Conferir o caminho antes de inserir evita mutação por chave incompatível.
        ancestral = posicao
        try:
            while ancestral > 0:
                ancestral = (ancestral - 1) // 2
                if not chave < self._chave(self._itens[ancestral]):
                    break
        except TypeError as erro:
            raise ValueError("Chaves não comparáveis.") from erro
        self._posicoes.inserir(item.id, posicao)
        try:
            self._itens.append(item)
        except MemoryError:
            self._posicoes.remover(item.id)
            raise
        self._subir(posicao)

    def extrair_minimo(self) -> Registro:
        if not self._itens:
            raise IndexError("Heap vazio.")
        return self.remover(self._itens[0].id)

    def remover(self, id: int) -> Registro:
        posicao = self._posicoes.buscar(id)
        if posicao is None:
            raise KeyError(id)
        removido = self._itens[posicao]
        ultima = len(self._itens) - 1
        if posicao != ultima:
            self._trocar(posicao, ultima)
        self._itens.pop()
        self._posicoes.remover(id)
        if posicao < len(self._itens):
            self._reordenar(posicao)
        return removido

    def atualizar(self, id: int) -> None:
        posicao = self._posicoes.buscar(id)
        if posicao is None:
            raise KeyError(id)
        self._reordenar(posicao)

    def validar(self) -> None:
        if type(self._itens) is not list or not callable(self._chave):
            raise ValueError("Armazenamento ou comparador inválido.")
        if not isinstance(self._posicoes, TabelaHash):
            raise ValueError("Índice de posições inválido.")
        self._posicoes.validar()
        if len(self._itens) != len(self._posicoes):
            raise ValueError("Quantidade de posições diverge do Heap.")
        for posicao, item in enumerate(self._itens):
            if type(getattr(item, "id", None)) is not int:
                raise ValueError("ID inválido.")
            registrada = self._posicoes.buscar(item.id)
            if type(registrada) is not int or registrada != posicao:
                raise ValueError("ID duplicado, ausente ou posição incorreta.")
            try:
                chave = self._chave(item)
                if not isinstance(chave, tuple):
                    raise ValueError("Chave inválida.")
                if posicao and chave < self._chave(self._itens[(posicao - 1) // 2]):
                    raise ValueError("Ordem do Min-Heap violada.")
            except (TypeError, AttributeError) as erro:
                raise ValueError("Chaves não comparáveis.") from erro
