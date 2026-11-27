"""Serviço central: estruturas próprias, reserva de IDs, cadastros e consultas."""

from datetime import datetime

from atendimentos.domain.atendimento import Atendimento
from atendimentos.domain.medico import Medico
from atendimentos.domain.paciente import Paciente
from atendimentos.structures.arvore_rubro_negra import ArvoreRubroNegra
from atendimentos.structures.min_heap import MinHeap
from atendimentos.structures.tabela_hash import TabelaHash


class SistemaAtendimento:
    """Base e cadastros das etapas SIGAE-19.3/19.4.

    Estruturas são internas: as views não devem acessá-las diretamente.
    IDs são únicos por tipo e por instância, reservados em sequência a partir
    de 1. Uma reserva é definitiva, mesmo sem criação do registro correspondente;
    remoções e falhas posteriores não devem retroceder os contadores.

    Instâncias distintas representam estados independentes. O provedor da
    instância compartilhada, o lock das operações (incluindo reservas) e o
    rollback centralizado serão implementados na SIGAE-20. Os cadastros usam
    compensação local das inserções. Esta base não é sincronizada
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

    @staticmethod
    def _compensar_insercoes(compensacoes, erro_original: Exception) -> None:
        """Desfaz tentativas em ordem inversa, inclusive inserção que lançou erro.

        A lista temporária registra apenas as remoções desta operação; não é
        um cadastro paralelo. Pressupõe índices recuperáveis pelas suas APIs.
        Falhas de compensação são propagadas, nunca apresentadas como sucesso.
        """
        erros = []
        for remover, chave in reversed(compensacoes):
            try:
                remover(chave)
            except KeyError:
                # A tentativa pode ter falhado antes de inserir o registro.
                pass
            except Exception as erro:
                erros.append(erro)
        if erros:
            raise ExceptionGroup(
                "Falha no cadastro e na compensação local.", [erro_original, *erros]
            ) from erro_original

    def cadastrar_paciente(self, nome: str, chegada: datetime, prioridade: int) -> Paciente:
        paciente = Paciente(self._reservar_id_paciente(), nome, chegada, prioridade)
        # A entidade valida todos os campos antes de qualquer alteração de índice.
        compensacoes = []
        try:
            compensacoes.append((self._pacientes.remover, paciente.id))
            self._pacientes.inserir(paciente.id, paciente)
            compensacoes.append((self._arvore_espera.remover, paciente.chave_chegada))
            self._arvore_espera.inserir(paciente.chave_chegada, paciente)
            compensacoes.append((self._heap_pacientes.remover, paciente.id))
            self._heap_pacientes.inserir(paciente)
        except Exception as erro:
            self._compensar_insercoes(compensacoes, erro)
            raise
        return paciente

    def cadastrar_medico(self, nome: str, registro: str) -> Medico:
        medico = Medico(self._reservar_id_medico(), nome, registro)
        compensacoes = []
        try:
            compensacoes.append((self._medicos.remover, medico.id))
            self._medicos.inserir(medico.id, medico)
            compensacoes.append((self._heap_medicos.remover, medico.id))
            self._heap_medicos.inserir(medico)
        except Exception as erro:
            self._compensar_insercoes(compensacoes, erro)
            raise
        return medico

    def buscar_paciente(self, id: int) -> Paciente | None:
        return self._pacientes.buscar(id)

    def buscar_medico(self, id: int) -> Medico | None:
        return self._medicos.buscar(id)

    def listar_pacientes(self) -> list[Paciente]:
        """Nova lista de referências de todos os pacientes, sem ordem garantida."""
        return self._pacientes.listar_valores()

    def listar_medicos(self) -> list[Medico]:
        """Nova lista de referências de todos os médicos, sem ordem garantida."""
        return self._medicos.listar_valores()

    def listar_fila(self) -> list[Paciente]:
        """Pacientes aguardando por chegada e ID, pelo percurso da árvore."""
        return self._arvore_espera.em_ordem()
