"""Compatibilidade com o caminho antigo da entidade Paciente.

A implementação mantida pelo projeto fica em atendimentos.domain.paciente.
"""

from atendimentos.domain.paciente import Paciente, SituacaoPaciente

__all__ = ["Paciente", "SituacaoPaciente"]
