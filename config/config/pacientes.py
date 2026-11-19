from dataclasses import dataclass
from datetime import datetime


@dataclass
class Paciente:
    id: int
    nome: str
    horario: datetime
    prioridade: int

    def __post_init__(self):
        if not self.nome.strip():
            raise ValueError("Nome obrigatório.")

        if not 1 <= self.prioridade <= 5:
            raise ValueError("Prioridade deve estar entre 1 e 5.")