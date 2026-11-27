"""Serviço central: estruturas próprias, reserva de IDs, cadastros e consultas."""

from datetime import datetime, timezone

from atendimentos.domain.atendimento import Atendimento
from atendimentos.domain.medico import Medico, SituacaoMedico
from atendimentos.domain.paciente import Paciente, SituacaoPaciente
from atendimentos.structures.arvore_rubro_negra import ArvoreRubroNegra
from atendimentos.structures.min_heap import MinHeap
from atendimentos.structures.tabela_hash import TabelaHash


class SistemaAtendimento:
    """Base e operações das etapas SIGAE-19.3 a SIGAE-19.6.

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

    def reclassificar_paciente(self, id: int, prioridade: int) -> Paciente:
        """Reclassifica a mesma entidade e reorganiza somente seu Heap.

        Consulta na Hash O(1) esperada, O(N) no pior caso (N cadastrados).
        Atualização O(log(n+1)) esperada, O(n log(n+1)) no pior caso devido
        às colisões da Hash de posições (n em espera). Espaço auxiliar O(1).
        A compensação repete a atualização, mantendo os mesmos limites.
        Pressupõe índice recuperável pela API; falhas de recuperação são explícitas.
        """
        paciente = self._pacientes.buscar(id)
        if paciente is None:
            raise KeyError(id)
        anterior = paciente.prioridade
        # A entidade rejeita prioridade/estado inválidos antes de qualquer mutação.
        paciente.reclassificar(prioridade)
        try:
            self._heap_pacientes.atualizar(id)
        except Exception as erro:
            try:
                paciente.reclassificar(anterior)
                self._heap_pacientes.atualizar(id)
            except Exception as recuperacao:
                raise ExceptionGroup(
                    "Falha na reclassificação e na compensação local.",
                    [erro, recuperacao],
                ) from erro
            raise
        return paciente

    def buscar_medico(self, id: int) -> Medico | None:
        return self._medicos.buscar(id)

    def chamar_proximo(self, inicio: datetime | None = None) -> Atendimento:
        """Seleciona ambos os mínimos e inicia um atendimento, sem concluir nenhum.

        Sem horário explícito, usa o instante atual em UTC. Ausência de paciente
        ou médico gera ValueError sem reservar ID nem alterar o estado.

        Para P/M cadastrados, p/m nos Heaps e A atendimentos: custo esperado
        amortizado O(log(p+1) + log(m+1)); pior caso
        O(P + M + p log(p+1) + m log(m+1) + A), incluindo colisões,
        realocações das listas e crescimento da Hash de atendimentos.
        Espaço auxiliar constante, exceto rehash O(A).

        A compensação local pressupõe estruturas recuperáveis por suas APIs.
        Confere os índices afetados: para n registros e b buckets em cada um,
        validar custa até O(b log(b+1) + n²) no Heap, O(b log(b+1) +
        n log(n+1)) na Hash e O(n) na árvore; espaço auxiliar O(b+n).
        Não há sincronização concorrente nesta etapa.
        """
        paciente = self._heap_pacientes.consultar_minimo()
        medico = self._heap_medicos.consultar_minimo()
        if paciente is None or medico is None:
            raise ValueError("É necessário haver paciente aguardando e médico disponível.")
        if (paciente.situacao != SituacaoPaciente.AGUARDANDO
                or medico.situacao != SituacaoMedico.DISPONIVEL):
            raise ValueError("Paciente ou médico em estado incompatível com a chamada.")
        if (self._pacientes.buscar(paciente.id) is not paciente
                or self._medicos.buscar(medico.id) is not medico
                or self._arvore_espera.buscar(paciente.chave_chegada) is not paciente):
            raise ValueError("Referências incompatíveis nos índices da chamada.")
        if inicio is None:
            inicio = datetime.now(timezone.utc)
        # Mesmas restrições temporais exigidas pelo médico, antes das mutações.
        if not isinstance(inicio, datetime) or inicio.utcoffset() is None:
            raise ValueError("O início deve ser uma data e horário com fuso horário.")
        try:
            inicio_utc = inicio.astimezone(timezone.utc)
        except (OverflowError, ValueError) as erro:
            raise ValueError("O início deve ser representável em UTC.") from erro
        if inicio_utc <= datetime.min.replace(tzinfo=timezone.utc):
            raise ValueError("O início deve ser posterior à data sentinela.")

        atendimento = Atendimento(self._reservar_id_atendimento(), paciente, medico, inicio)
        estado_paciente = paciente.situacao
        estado_medico = medico.situacao
        ultima_atribuicao = medico.ultima_atribuicao
        compensacoes = []  # Registro temporário de recuperação, não é um índice.

        def restaurar_heap(heap, item):
            # Normaliza tanto a falha anterior quanto a posterior à remoção.
            try:
                heap.remover(item.id)
            except KeyError:
                pass
            heap.inserir(item)

        def restaurar_arvore():
            if self._arvore_espera.buscar(paciente.chave_chegada) is None:
                self._arvore_espera.inserir(paciente.chave_chegada, paciente)

        def restaurar_medico():
            # Restauração interna não representa uma transição de negócio.
            medico._situacao = estado_medico
            medico._ultima_atribuicao = ultima_atribuicao

        def remover_atendimento():
            try:
                self._atendimentos.remover(atendimento.id)
            except KeyError:
                pass

        try:
            # Registrar antes da tentativa cobre exceções após a mutação.
            compensacoes.append(lambda: restaurar_heap(self._heap_pacientes, paciente))
            self._heap_pacientes.remover(paciente.id)
            compensacoes.append(restaurar_arvore)
            self._arvore_espera.remover(paciente.chave_chegada)
            compensacoes.append(lambda: restaurar_heap(self._heap_medicos, medico))
            self._heap_medicos.remover(medico.id)
            compensacoes.append(lambda: setattr(paciente, "_situacao", estado_paciente))
            paciente.iniciar_atendimento()
            compensacoes.append(restaurar_medico)
            medico.iniciar_atendimento(inicio)
            compensacoes.append(remover_atendimento)
            self._atendimentos.inserir(atendimento.id, atendimento)
        except Exception as erro:
            erros = []
            for compensar in reversed(compensacoes):
                try:
                    compensar()
                except Exception as recuperacao:
                    erros.append(recuperacao)
            for indice in (self._heap_pacientes, self._arvore_espera,
                           self._heap_medicos, self._atendimentos):
                try:
                    indice.validar()
                except Exception as recuperacao:
                    erros.append(recuperacao)
            if erros:
                raise ExceptionGroup(
                    "Falha na chamada e na compensação local.", [erro, *erros]
                ) from erro
            raise
        return atendimento

    def listar_pacientes(self) -> list[Paciente]:
        """Nova lista de referências de todos os pacientes, sem ordem garantida."""
        return self._pacientes.listar_valores()

    def listar_medicos(self) -> list[Medico]:
        """Nova lista de referências de todos os médicos, sem ordem garantida."""
        return self._medicos.listar_valores()

    def listar_fila(self) -> list[Paciente]:
        """Pacientes aguardando por chegada e ID, pelo percurso da árvore."""
        return self._arvore_espera.em_ordem()
