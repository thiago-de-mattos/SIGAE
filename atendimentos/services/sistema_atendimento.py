"""Base do serviço central: estruturas próprias e reserva de IDs por instância."""

from atendimentos.domain.atendimento import Atendimento
from atendimentos.domain.medico import Medico
from atendimentos.domain.paciente import Paciente
from atendimentos.structures.arvore_rubro_negra import ArvoreRubroNegra
from atendimentos.structures.min_heap import MinHeap
from atendimentos.structures.tabela_hash import TabelaHash


class SistemaAtendimento:
    """Base da SIGAE-19.3, ainda sem operações de negócio.

    Estruturas são internas: as views não devem acessá-las diretamente.
    IDs são únicos por tipo e por instância, reservados em sequência a partir
    de 1. Uma reserva é definitiva, mesmo sem criação do registro correspondente;
    remoções e falhas posteriores não devem retroceder os contadores.

    Instâncias distintas representam estados independentes. O provedor da
    instância compartilhada, o lock das operações (incluindo reservas) e o
    rollback serão implementados na SIGAE-20. Esta base não é sincronizada
    para uso concorrente e não persiste dados entre execuções.
    """

    def __init__(self) -> None:
        self._pacientes = TabelaHash[Paciente]()
        self._medicos = TabelaHash[Medico]()
        self._atendimentos = TabelaHash[Atendimento]()
        self._arvore_espera = ArvoreRubroNegra()
        self._heap_pacientes = MinHeap[Paciente](lambda paciente: paciente.chave_prioridade)
        self._heap_medicos = MinHeap[Medico](lambda medico: medico.chave_prioridade)
        self._ultimo_id_paciente = 0
        self._ultimo_id_medico = 0
        self._ultimo_id_atendimento = 0

    def _reservar_id_paciente(self) -> int:
        self._ultimo_id_paciente += 1
        return self._ultimo_id_paciente

    def _reservar_id_medico(self) -> int:
        self._ultimo_id_medico += 1
        return self._ultimo_id_medico

    def _reservar_id_atendimento(self) -> int:
        self._ultimo_id_atendimento += 1
        return self._ultimo_id_atendimento
