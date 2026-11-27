"""Registro de atendimento; a coordenação das entidades pertence ao serviço."""

from datetime import datetime
from enum import StrEnum

from .medico import Medico
from .paciente import Paciente


class SituacaoAtendimento(StrEnum):
    EM_ATENDIMENTO = "em_atendimento"
    CONCLUIDO = "concluido"
    CANCELADO = "cancelado"


class Atendimento:
    def __init__(self, id: int, paciente: Paciente, medico: Medico, inicio: datetime):
        if type(id) is not int or id <= 0:
            raise ValueError("O ID deve ser um número inteiro positivo.")
        if not isinstance(paciente, Paciente):
            raise ValueError("O paciente deve ser uma entidade Paciente válida.")
        if not isinstance(medico, Medico):
            raise ValueError("O médico deve ser uma entidade Medico válida.")
        self._validar_horario(inicio)

        self._id = id
        self._paciente = paciente
        self._medico = medico
        self._inicio = inicio
        self._fim: datetime | None = None
        self._situacao = SituacaoAtendimento.EM_ATENDIMENTO

    @staticmethod
    def _validar_horario(horario: datetime) -> None:
        if not isinstance(horario, datetime) or horario.utcoffset() is None:
            raise ValueError("O horário deve ser uma data e horário com fuso horário.")

    @property
    def id(self) -> int:
        return self._id

    @property
    def paciente(self) -> Paciente:
        return self._paciente

    @property
    def medico(self) -> Medico:
        return self._medico

    @property
    def inicio(self) -> datetime:
        return self._inicio

    @property
    def fim(self) -> datetime | None:
        return self._fim

    @property
    def situacao(self) -> SituacaoAtendimento:
        return self._situacao

    def _encerrar(self, fim: datetime, situacao: SituacaoAtendimento) -> None:
        if self.situacao != SituacaoAtendimento.EM_ATENDIMENTO:
            raise ValueError("Somente um atendimento ativo pode ser encerrado.")
        self._validar_horario(fim)
        if fim < self.inicio:
            raise ValueError("O encerramento não pode anteceder o início.")
        self._fim = fim
        self._situacao = situacao

    def concluir(self, fim: datetime) -> None:
        self._encerrar(fim, SituacaoAtendimento.CONCLUIDO)

    def cancelar(self, fim: datetime) -> None:
        self._encerrar(fim, SituacaoAtendimento.CANCELADO)

    def __str__(self) -> str:
        return f"{self.id} - {self.paciente.nome} / {self.medico.nome}"
