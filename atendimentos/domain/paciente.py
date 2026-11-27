from datetime import datetime, timezone
from enum import StrEnum


class SituacaoPaciente(StrEnum):
    AGUARDANDO = "aguardando"
    EM_ATENDIMENTO = "em_atendimento"
    CONCLUIDO = "concluido"
    CANCELADO = "cancelado"


class Paciente:
    def __init__(
        self,
        id: int,
        nome: str,
        chegada: datetime,
        prioridade: int,
    ):
        if type(id) is not int or id <= 0:
            raise ValueError("O ID deve ser um número inteiro positivo.")

        if not isinstance(nome, str) or not nome.strip():
            raise ValueError("O nome do paciente é obrigatório.")

        if not isinstance(chegada, datetime):
            raise ValueError("A chegada deve ser uma data e horário.")

        if chegada.utcoffset() is None:
            raise ValueError("O horário de chegada deve possuir fuso horário.")

        try:
            chegada_utc = chegada.astimezone(timezone.utc)
        except (OverflowError, ValueError) as erro:
            raise ValueError("O horário de chegada deve ser representável em UTC.") from erro

        self._validar_prioridade(prioridade)

        self._id = id
        self._nome = nome.strip()
        self._chegada = chegada
        self._chegada_utc = chegada_utc
        self._prioridade = prioridade
        self._situacao = SituacaoPaciente.AGUARDANDO

    @staticmethod
    def _validar_prioridade(prioridade: int) -> None:
        if type(prioridade) is not int or not 1 <= prioridade <= 5:
            raise ValueError("A prioridade deve ser um inteiro entre 1 e 5.")

    @property
    def id(self) -> int:
        return self._id

    @property
    def nome(self) -> str:
        return self._nome

    @property
    def chegada(self) -> datetime:
        return self._chegada

    @property
    def prioridade(self) -> int:
        return self._prioridade

    @property
    def situacao(self) -> SituacaoPaciente:
        return self._situacao

    @property
    def chave_chegada(self) -> tuple[datetime, int]:
        return self._chegada_utc, self.id

    @property
    def chave_prioridade(self) -> tuple[int, datetime, int]:
        return self.prioridade, *self.chave_chegada

    def reclassificar(self, prioridade: int) -> None:
        if self.situacao != SituacaoPaciente.AGUARDANDO:
            raise ValueError("Somente pacientes aguardando podem ser reclassificados.")

        self._validar_prioridade(prioridade)
        self._prioridade = prioridade

    def iniciar_atendimento(self) -> None:
        if self.situacao != SituacaoPaciente.AGUARDANDO:
            raise ValueError("Somente pacientes aguardando podem iniciar atendimento.")

        self._situacao = SituacaoPaciente.EM_ATENDIMENTO

    def concluir_atendimento(self) -> None:
        if self.situacao != SituacaoPaciente.EM_ATENDIMENTO:
            raise ValueError("O paciente precisa estar em atendimento para concluir.")

        self._situacao = SituacaoPaciente.CONCLUIDO

    def cancelar(self) -> None:
        if self.situacao not in (
            SituacaoPaciente.AGUARDANDO,
            SituacaoPaciente.EM_ATENDIMENTO,
        ):
            raise ValueError("O paciente já possui um registro encerrado.")

        self._situacao = SituacaoPaciente.CANCELADO

    def __str__(self) -> str:
        return f"{self.id} - {self.nome}"