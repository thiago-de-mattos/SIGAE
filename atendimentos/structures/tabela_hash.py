"""Base da Hash própria (SIGAE-14), independente das entidades e do Django."""

from typing import Generic, TypeVar


Valor = TypeVar("Valor")


class TabelaHash(Generic[Valor]):
    """Encadeamento separado em listas de pares (chave, referência ao valor).

    As listas são o armazenamento dos buckets, não um índice pronto.
    Remoção e redimensionamento ficam para SIGAE-15; validar() para SIGAE-16.
    Esta base ainda não implementa todo o ContratoHash, incluindo atualizar()
    e listar_valores(). O fator de carga é reservado para o redimensionamento.
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

        bucket.append((chave, valor))
        self._quantidade += 1

    def buscar(self, chave: int) -> Valor | None:
        """Retorna a referência armazenada ou None quando a chave não existe."""
        for chave_existente, valor in self._buckets[self._indice(chave)]:
            if chave_existente == chave:
                return valor
        return None

    def __len__(self) -> int:
        return self._quantidade
