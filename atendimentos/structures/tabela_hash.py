"""Hash própria, independente das entidades e do Django."""

from typing import Generic, TypeVar


Valor = TypeVar("Valor")


class TabelaHash(Generic[Valor]):
    """Encadeamento separado em listas de pares (chave, referência ao valor).

    As listas são o armazenamento dos buckets, não um índice pronto.
    Cresce por duplicação ao ultrapassar o fator de carga máximo; não encolhe.
    A validação estrutural completa (validar) fica para SIGAE-16.
    """

    def __init__(
        self, capacidade: int = 11, fator_carga_maximo: float = 0.75
    ) -> None:
        if type(capacidade) is not int or capacidade <= 0:
            raise ValueError("A capacidade deve ser um inteiro positivo.")
        if (
            type(fator_carga_maximo) not in (int, float)
            or not 0 < fator_carga_maximo < float("inf")
        ):
            raise ValueError("O fator de carga máximo deve ser positivo e finito.")

        self._capacidade = capacidade
        self._fator_carga_maximo = fator_carga_maximo
        self._buckets: list[list[tuple[int, Valor]]] = [
            [] for _ in range(capacidade)
        ]
        self._quantidade = 0

    def _indice(self, chave: int) -> int:
        if type(chave) is not int:
            raise ValueError("A chave deve ser um número inteiro.")
        return chave % self._capacidade

    def inserir(self, chave: int, valor: Valor) -> None:
        """Insere sem sobrescrever; duplicidade ou valor None gera ValueError."""
        indice = self._indice(chave)
        if valor is None:
            raise ValueError("None é reservado para consultas sem resultado.")

        bucket = self._buckets[indice]
        for chave_existente, _ in bucket:
            if chave_existente == chave:
                raise ValueError("A chave já está cadastrada.")

        quantidade = self._quantidade + 1
        capacidade = self._capacidade
        while quantidade / capacidade > self._fator_carga_maximo:
            capacidade *= 2

        if capacidade != self._capacidade:
            # Preparar também a inserção antes de publicar a nova tabela.
            # Uma falha de alocação não descarta os buckets originais.
            buckets = self._rehash(capacidade)
            buckets[chave % capacidade].append((chave, valor))
            self._buckets = buckets
            self._capacidade = capacidade
        else:
            bucket.append((chave, valor))
        self._quantidade = quantidade

    def _rehash(self, capacidade: int) -> list[list[tuple[int, Valor]]]:
        """Redistribui referências sem inserir novamente nem mudar a quantidade."""
        buckets: list[list[tuple[int, Valor]]] = [[] for _ in range(capacidade)]
        for bucket in self._buckets:
            for chave, valor in bucket:
                buckets[chave % capacidade].append((chave, valor))
        return buckets

    def buscar(self, chave: int) -> Valor | None:
        """Retorna a referência armazenada ou None quando a chave não existe."""
        for chave_existente, valor in self._buckets[self._indice(chave)]:
            if chave_existente == chave:
                return valor
        return None

    def remover(self, chave: int) -> Valor:
        """Remove somente a chave pedida; ausência gera KeyError."""
        bucket = self._buckets[self._indice(chave)]
        for posicao, (chave_existente, valor) in enumerate(bucket):
            if chave_existente == chave:
                del bucket[posicao]
                self._quantidade -= 1
                return valor
        raise KeyError(chave)

    def atualizar(self, chave: int, valor: Valor) -> None:
        """Substitui a referência de uma chave existente, sem alterar quantidade."""
        bucket = self._buckets[self._indice(chave)]
        if valor is None:
            raise ValueError("None é reservado para consultas sem resultado.")
        for posicao, (chave_existente, _) in enumerate(bucket):
            if chave_existente == chave:
                bucket[posicao] = (chave, valor)
                return
        raise KeyError(chave)

    def listar_valores(self) -> list[Valor]:
        """Nova lista de referências, sem garantia de ordem."""
        return [valor for bucket in self._buckets for _, valor in bucket]

    def __len__(self) -> int:
        return self._quantidade
