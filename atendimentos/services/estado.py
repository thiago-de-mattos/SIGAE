"""Instância compartilhada por todas as requisições do processo Django."""

from threading import Lock

from .sistema_atendimento import SistemaAtendimento


_lock_inicializacao = Lock()
_sistema = None


def obter_sistema() -> SistemaAtendimento:
    global _sistema
    with _lock_inicializacao:
        if _sistema is None:
            _sistema = SistemaAtendimento()
        return _sistema
