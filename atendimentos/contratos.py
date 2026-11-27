"""Interfaces das estruturas; os algoritmos serão implementados separadamente."""

from datetime import datetime
from typing import Protocol, TypeVar

from .domain.paciente import Paciente


class Identificavel(Protocol):
    @property
    def id(self) -> int: ...


Valor = TypeVar("Valor")
Registro = TypeVar("Registro", bound=Identificavel)
ChaveChegada = tuple[datetime, int]


class ContratoHash(Protocol[Valor]):
    """IDs inteiros; inserir duplicado gera ValueError; chave ausente gera KeyError.

    A exceção à regra de ausência é buscar(), que retorna None.
    None não é um valor armazenável, pois representa ausência.
    """

    def inserir(self, chave: int, valor: Valor) -> None: ...

    def buscar(self, chave: int) -> Valor | None: ...

    def atualizar(self, chave: int, valor: Valor) -> None: ...

    def remover(self, chave: int) -> Valor: ...

    def listar_valores(self) -> list[Valor]: ...

    def __len__(self) -> int: ...

    def validar(self) -> None:
        """Levanta ValueError se encontrar uma inconsistência interna."""
        ...


class ContratoHeap(Protocol[Registro]):
    """Min-Heap com comparador configurável e controle interno de posições.

    IDs duplicados geram ValueError. Remover/atualizar ID ausente gera KeyError.
    A implementação mantém ID -> posição em uma Hash própria, sem varredura.
    O comparador deve produzir a chave de pacientes ou de médicos disponíveis.
    """

    def inserir(self, item: Registro) -> None: ...

    def consultar_minimo(self) -> Registro | None: ...

    def extrair_minimo(self) -> Registro:
        """Levanta IndexError quando o Heap está vazio."""
        ...

    def remover(self, id: int) -> Registro: ...

    def atualizar(self, id: int) -> None:
        """Reorganiza após mudança da chave; o serviço coordena a operação."""
        ...

    def __len__(self) -> int: ...

    def validar(self) -> None:
        """Confere ordem e mapa de posições; inconsistência gera ValueError."""
        ...


class ContratoArvore(Protocol):
    """Índice de espera por (chegada, ID), sem depender da prioridade clínica.

    Inserção duplicada ou chave diferente da chave_chegada gera ValueError.
    Remover chave ausente gera KeyError. Buscar chave ausente retorna None.
    """

    def inserir(self, chave: ChaveChegada, paciente: Paciente) -> None: ...

    def buscar(self, chave: ChaveChegada) -> Paciente | None: ...

    def remover(self, chave: ChaveChegada) -> Paciente: ...

    def em_ordem(self) -> list[Paciente]: ...

    def __len__(self) -> int: ...

    def validar(self) -> None:
        """Confere ordenação e propriedades rubro-negras; erro gera ValueError."""
        ...
