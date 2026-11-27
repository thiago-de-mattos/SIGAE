"""Entidade médico; geração de IDs e coordenação de índices cabem ao serviço."""

from datetime import datetime, timezone
from enum import StrEnum


_SEM_ATRIBUICAO = datetime.min.replace(tzinfo=timezone.utc)


class SituacaoMedico(StrEnum):
    DISPONIVEL = "disponivel"
    EM_ATENDIMENTO = "em_atendimento"


class Medico:
    def __init__(self, id: int, nome: str, registro: str):
        if type(id) is not int or id <= 0:
            raise ValueError("O ID deve ser um número inteiro positivo.")
        if not isinstance(nome, str) or not nome.strip():
            raise ValueError("O nome do médico é obrigatório.")
        if not isinstance(registro, str) or not registro.strip():
            raise ValueError("O registro profissional fictício é obrigatório.")

        self._id = id
        self._nome = nome.strip()
        self._registro = registro.strip()
        self._situacao = SituacaoMedico.DISPONIVEL
        self._total_concluidos = 0
        self._ultima_atribuicao: datetime | None = None

    @property
    def id(self) -> int:
        return self._id

    @property
    def nome(self) -> str:
        return self._nome

    @property
    def registro(self) -> str:
        return self._registro

    @property
    def situacao(self) -> SituacaoMedico:
        return self._situacao

    @property
    def total_concluidos(self) -> int:
        return self._total_concluidos

    @property
    def ultima_atribuicao(self) -> datetime | None:
        return self._ultima_atribuicao

    @property
    def chave_prioridade(self) -> tuple[int, datetime, int]:
        """Menor carga, atribuição mais antiga e menor ID; nunca atribuídos primeiro."""
        return (
            self.total_concluidos,
            self.ultima_atribuicao if self.ultima_atribuicao is not None else _SEM_ATRIBUICAO,
            self.id,
        )

    def iniciar_atendimento(self, inicio: datetime) -> None:
        if self.situacao != SituacaoMedico.DISPONIVEL:
            raise ValueError("Somente médicos disponíveis podem iniciar atendimento.")
        if not isinstance(inicio, datetime) or inicio.utcoffset() is None:
            raise ValueError("O início deve ser uma data e horário com fuso horário.")
        try:
            inicio_utc = inicio.astimezone(timezone.utc)
        except (OverflowError, ValueError) as erro:
            raise ValueError("O início deve ser representável em UTC.") from erro
        # Reserva exclusiva da sentinela: toda atribuição válida deve ser posterior.
        if inicio_utc <= _SEM_ATRIBUICAO:
            raise ValueError("O início deve ser posterior à data sentinela.")
        self._ultima_atribuicao = inicio_utc
        self._situacao = SituacaoMedico.EM_ATENDIMENTO

    def concluir_atendimento(self) -> None:
        if self.situacao != SituacaoMedico.EM_ATENDIMENTO:
            raise ValueError("O médico precisa estar em atendimento para concluir.")
        self._total_concluidos += 1
        self._situacao = SituacaoMedico.DISPONIVEL

    def cancelar_atendimento(self) -> None:
        if self.situacao != SituacaoMedico.EM_ATENDIMENTO:
            raise ValueError("O médico precisa estar em atendimento para cancelar.")
        self._situacao = SituacaoMedico.DISPONIVEL

    def __str__(self) -> str:
        return f"{self.id} - {self.nome}"
