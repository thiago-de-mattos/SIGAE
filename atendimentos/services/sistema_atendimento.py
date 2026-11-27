"""Serviço central: estruturas próprias, reserva de IDs, cadastros e consultas."""

from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
import logging
from threading import RLock

from atendimentos.domain.atendimento import Atendimento, SituacaoAtendimento
from atendimentos.domain.medico import Medico, SituacaoMedico
from atendimentos.domain.paciente import Paciente, SituacaoPaciente
from atendimentos.structures.arvore_rubro_negra import ArvoreRubroNegra
from atendimentos.structures.min_heap import MinHeap
from atendimentos.structures.tabela_hash import TabelaHash


logger = logging.getLogger(__name__)


class SistemaIndisponivel(RuntimeError):
    """O serviço não pode garantir a consistência do estado."""


def sincronizado(metodo):
    @wraps(metodo)
    def executar(self, *args, **kwargs):
        with self.leitura():
            return metodo(self, *args, **kwargs)

    return executar


class SistemaAtendimento:
    """Coordena os índices em memória e reserva IDs sob um único lock."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._indisponivel = False
        self._pacientes = TabelaHash[Paciente]()
        self._medicos = TabelaHash[Medico]()
        self._atendimentos = TabelaHash[Atendimento]()
        self._arvore_espera = ArvoreRubroNegra()
        self._heap_pacientes = MinHeap[Paciente](lambda paciente: paciente.chave_prioridade)
        self._heap_medicos = MinHeap[Medico](lambda medico: medico.chave_prioridade)
        self._ultimo_id_paciente = 0
        self._ultimo_id_medico = 0
        self._ultimo_id_atendimento = 0

    @contextmanager
    def leitura(self):
        """Mantém as referências estáveis enquanto o chamador coleta os dados."""
        with self._lock:
            if self._indisponivel:
                raise SistemaIndisponivel("O sistema de atendimento está indisponível.")
            yield

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
    def _remover_se_presente(indice, chave):
        try:
            indice.remover(chave)
        except KeyError:
            pass

    @sincronizado
    def cadastrar_paciente(self, nome: str, chegada: datetime, prioridade: int) -> Paciente:
        paciente = Paciente(self._reservar_id_paciente(), nome, chegada, prioridade)
        # A entidade valida todos os campos antes de qualquer alteração de índice.
        compensacoes = []
        try:
            compensacoes.append(lambda: self._remover_se_presente(self._pacientes, paciente.id))
            self._pacientes.inserir(paciente.id, paciente)
            compensacoes.append(lambda: self._remover_se_presente(self._arvore_espera, paciente.chave_chegada))
            self._arvore_espera.inserir(paciente.chave_chegada, paciente)
            compensacoes.append(lambda: self._remover_se_presente(self._heap_pacientes, paciente.id))
            self._heap_pacientes.inserir(paciente)
        except Exception as erro:
            self._compensar_operacao(compensacoes, erro)
            raise
        return paciente

    @sincronizado
    def cadastrar_medico(self, nome: str, registro: str) -> Medico:
        medico = Medico(self._reservar_id_medico(), nome, registro)
        compensacoes = []
        try:
            compensacoes.append(lambda: self._remover_se_presente(self._medicos, medico.id))
            self._medicos.inserir(medico.id, medico)
            compensacoes.append(lambda: self._remover_se_presente(self._heap_medicos, medico.id))
            self._heap_medicos.inserir(medico)
        except Exception as erro:
            self._compensar_operacao(compensacoes, erro)
            raise
        return medico

    @sincronizado
    def buscar_paciente(self, id: int) -> Paciente | None:
        return self._pacientes.buscar(id)

    @sincronizado
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
            self._compensar_operacao(
                [lambda: self._heap_pacientes.atualizar(id),
                 lambda: paciente.reclassificar(anterior)],
                erro,
            )
            raise
        return paciente

    @sincronizado
    def buscar_medico(self, id: int) -> Medico | None:
        return self._medicos.buscar(id)

    @sincronizado
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

        if inicio_utc < paciente.chave_chegada[0]:
            raise ValueError("O início não pode anteceder a chegada do paciente.")

        atendimento = Atendimento(self._reservar_id_atendimento(), paciente, medico, inicio)
        estado_paciente = paciente.situacao
        estado_medico = medico.situacao
        ultima_atribuicao = medico.ultima_atribuicao
        compensacoes = []  # Registro temporário de recuperação, não é um índice.

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
            compensacoes.append(lambda: self._restaurar_heap(self._heap_pacientes, paciente))
            self._heap_pacientes.remover(paciente.id)
            compensacoes.append(restaurar_arvore)
            self._arvore_espera.remover(paciente.chave_chegada)
            compensacoes.append(lambda: self._restaurar_heap(self._heap_medicos, medico))
            self._heap_medicos.remover(medico.id)
            compensacoes.append(lambda: setattr(paciente, "_situacao", estado_paciente))
            paciente.iniciar_atendimento()
            compensacoes.append(restaurar_medico)
            medico.iniciar_atendimento(inicio)
            compensacoes.append(remover_atendimento)
            self._atendimentos.inserir(atendimento.id, atendimento)
        except Exception as erro:
            self._compensar_operacao(compensacoes, erro)
            raise
        return atendimento

    @staticmethod
    def _restaurar_heap(heap, item):
        """Normaliza presença após falha anterior ou posterior à remoção."""
        try:
            heap.remover(item.id)
        except KeyError:
            pass
        heap.inserir(item)

    def _compensar_operacao(self, compensacoes, erro):
        """Desfaz etapas e bloqueia o serviço se a recuperação não for confiável."""
        erros = []
        for compensar in reversed(compensacoes):
            try:
                compensar()
            except Exception as recuperacao:
                erros.append(recuperacao)
        try:
            self.validar_indices()
        except Exception as recuperacao:
            erros.append(recuperacao)
        if erros:
            self._indisponivel = True
            falha = ExceptionGroup("Falha na operação e na compensação local.", [erro, *erros])
            logger.error("Estado do SIGAE bloqueado após falha de recuperação.", exc_info=falha)
            raise falha from erro

    @sincronizado
    def validar_indices(self) -> None:
        """Verifica os índices, os vínculos ativos e os totais médicos."""
        for indice in (self._pacientes, self._medicos, self._atendimentos,
                       self._arvore_espera, self._heap_pacientes, self._heap_medicos):
            indice.validar()

        pacientes = self.listar_pacientes()
        medicos = self.listar_medicos()
        espera = {p for p in pacientes if p.situacao == SituacaoPaciente.AGUARDANDO}
        disponiveis = {m for m in medicos if m.situacao == SituacaoMedico.DISPONIVEL}
        if (set(self.listar_fila()) != espera
                or set(self._heap_pacientes.listar_itens()) != espera
                or set(self._heap_medicos.listar_itens()) != disponiveis):
            raise ValueError("As filas não correspondem aos cadastros elegíveis.")

        ativos_pacientes = Counter()
        ativos_medicos = Counter()
        concluidos = Counter()
        for atendimento in self._atendimentos.listar_valores():
            paciente, medico = atendimento.paciente, atendimento.medico
            if self.buscar_paciente(paciente.id) is not paciente or self.buscar_medico(medico.id) is not medico:
                raise ValueError("Atendimento com referência incompatível.")
            if atendimento.situacao == SituacaoAtendimento.EM_ATENDIMENTO:
                ativos_pacientes[paciente] += 1
                ativos_medicos[medico] += 1
            if atendimento.situacao == SituacaoAtendimento.CONCLUIDO:
                concluidos[medico] += 1
            if atendimento.situacao.value != paciente.situacao.value:
                raise ValueError("Situação do atendimento incompatível com a do paciente.")

        if (any(ativos_pacientes[p] != (p.situacao == SituacaoPaciente.EM_ATENDIMENTO) for p in pacientes)
                or any(ativos_medicos[m] != (m.situacao == SituacaoMedico.EM_ATENDIMENTO) for m in medicos)
                or any(concluidos[m] != m.total_concluidos for m in medicos)):
            raise ValueError("Atendimentos ativos ou contadores incompatíveis.")

    @staticmethod
    def _horario_encerramento(fim, inicio):
        if fim is None:
            fim = datetime.now(timezone.utc)
        if Atendimento._validar_horario(fim) < inicio:
            raise ValueError("O encerramento não pode anteceder o início.")
        return fim

    @sincronizado
    def concluir_atendimento(self, id: int, fim: datetime | None = None) -> Atendimento:
        """Encerra pela Hash, contando exatamente uma conclusão.

        Com A atendimentos, P/M cadastrados e m médicos disponíveis, custo
        esperado amortizado O(log(m+1)); pior O(A+P+M+m log(m+1)), incluindo
        colisões e eventual rehash da Hash de posições. Espaço O(1), exceto
        realocação/rehash O(m). Recuperação: custos de _compensar_operacao.
        """
        atendimento = self._atendimentos.buscar(id)
        if atendimento is None:
            raise KeyError(id)
        self._encerrar_atendimento(atendimento, fim, concluir=True)
        return atendimento

    @sincronizado
    def cancelar_atendimento(self, id: int, fim: datetime | None = None) -> Atendimento:
        atendimento = self._atendimentos.buscar(id)
        if atendimento is None:
            raise KeyError(id)
        self._encerrar_atendimento(atendimento, fim, concluir=False)
        return atendimento

    def _encerrar_atendimento(self, atendimento, fim, *, concluir):
        paciente, medico = atendimento.paciente, atendimento.medico
        if (atendimento.situacao != SituacaoAtendimento.EM_ATENDIMENTO
                or paciente.situacao != SituacaoPaciente.EM_ATENDIMENTO
                or medico.situacao != SituacaoMedico.EM_ATENDIMENTO):
            raise ValueError("O atendimento, paciente e médico devem estar em atendimento.")
        if (self._pacientes.buscar(paciente.id) is not paciente
                or self._medicos.buscar(medico.id) is not medico):
            raise ValueError("Referências incompatíveis nos cadastros.")
        fim = self._horario_encerramento(fim, atendimento.chave_inicio[0])
        # Apenas valores para restauração; mantém as referências originais.
        anterior = (atendimento.situacao, atendimento.fim, paciente.situacao,
                    medico.situacao, medico.total_concluidos, medico.ultima_atribuicao)

        def restaurar_entidades():
            (atendimento._situacao, atendimento._fim, paciente._situacao,
             medico._situacao, medico._total_concluidos, medico._ultima_atribuicao) = anterior

        def retirar_medico():
            try:
                self._heap_medicos.remover(medico.id)
            except KeyError:
                pass

        compensacoes = [restaurar_entidades]
        try:
            if concluir:
                atendimento.concluir(fim)
                paciente.concluir_atendimento()
                medico.concluir_atendimento()
            else:
                atendimento.cancelar(fim)
                paciente.cancelar()
                medico.cancelar_atendimento()
            compensacoes.append(retirar_medico)
            self._heap_medicos.inserir(medico)
        except Exception as erro:
            self._compensar_operacao(compensacoes, erro)
            raise

    @sincronizado
    def cancelar_paciente(self, id: int, fim: datetime | None = None) -> Paciente:
        """Cancela espera ou atendimento ativo, preservando todos os cadastros.

        Na espera, valida fim >= chegada, mas não cria atendimento nem grava
        horário na entidade Paciente, que não possui esse campo.
        Custo esperado amortizado O(log(p+1)), pior O(P+p log(p+1)), com P
        cadastrados e p em espera. Espaço O(1), salvo realocações na recuperação.

        Para paciente ativo, percorre listar_valores da Hash de atendimentos:
        O(B+A) tempo e O(A) espaço, B buckets e A registros históricos.
        A lista temporária de referências não substitui um índice próprio.
        Evita adicionar/sincronizar um novo índice nesta etapa e detecta vínculos
        ativos ausentes ou duplicados. Soma o custo de _encerrar_atendimento
        (Heap esperado amortizado O(log(m+1)), pior O(P+M+m log(m+1))).
        Recuperação acrescenta os custos de _compensar_operacao.
        """
        paciente = self._pacientes.buscar(id)
        if paciente is None:
            raise KeyError(id)
        if paciente.situacao == SituacaoPaciente.EM_ATENDIMENTO:
            ativo = None
            for atendimento in self._atendimentos.listar_valores():
                if (atendimento.paciente is paciente
                        and atendimento.situacao == SituacaoAtendimento.EM_ATENDIMENTO):
                    if ativo is not None:
                        raise ValueError("Paciente possui mais de um atendimento ativo.")
                    ativo = atendimento
            if ativo is None:
                raise ValueError("Paciente sem atendimento ativo vinculado.")
            self._encerrar_atendimento(ativo, fim, concluir=False)
            return paciente
        if paciente.situacao != SituacaoPaciente.AGUARDANDO:
            raise ValueError("Somente pacientes aguardando ou em atendimento podem ser cancelados.")
        self._horario_encerramento(fim, paciente.chave_chegada[0])
        if self._arvore_espera.buscar(paciente.chave_chegada) is not paciente:
            raise ValueError("Paciente ausente do índice cronológico.")
        anterior = paciente.situacao
        compensacoes = []

        def restaurar_arvore():
            if self._arvore_espera.buscar(paciente.chave_chegada) is None:
                self._arvore_espera.inserir(paciente.chave_chegada, paciente)

        try:
            compensacoes.append(lambda: self._restaurar_heap(self._heap_pacientes, paciente))
            self._heap_pacientes.remover(paciente.id)
            compensacoes.append(restaurar_arvore)
            self._arvore_espera.remover(paciente.chave_chegada)
            compensacoes.append(lambda: setattr(paciente, "_situacao", anterior))
            paciente.cancelar()
        except Exception as erro:
            self._compensar_operacao(compensacoes, erro)
            raise
        return paciente

    @sincronizado
    def listar_pacientes(self) -> list[Paciente]:
        """Nova lista de referências de todos os pacientes, sem ordem garantida."""
        return self._pacientes.listar_valores()

    @sincronizado
    def listar_medicos(self) -> list[Medico]:
        """Nova lista de referências de todos os médicos, sem ordem garantida."""
        return self._medicos.listar_valores()

    @sincronizado
    def listar_fila(self) -> list[Paciente]:
        """Espera por chegada e ID via árvore; tempo e espaço O(n), n em espera."""
        return self._arvore_espera.em_ordem()

    @sincronizado
    def consultar_proximo_paciente(self) -> Paciente | None:
        """Referência ao mínimo clínico, ou None; tempo e espaço O(1)."""
        return self._heap_pacientes.consultar_minimo()

    @sincronizado
    def consultar_proximo_medico(self) -> Medico | None:
        """Referência ao médico elegível mínimo, ou None; tempo e espaço O(1)."""
        return self._heap_medicos.consultar_minimo()

    @sincronizado
    def listar_atendimentos_ativos(self) -> list[Atendimento]:
        """Referências aos ativos, sem ordem garantida.

        Para A atendimentos e B buckets: tempo O(B+A), espaço O(A).
        """
        return [a for a in self._atendimentos.listar_valores()
                if a.situacao == SituacaoAtendimento.EM_ATENDIMENTO]

    @sincronizado
    def listar_historico(self) -> list[Atendimento]:
        """Encerrados por (início, ID), conforme a arquitetura.

        As referências expõem ID, paciente, médico, situação, início e fim.
        Ativos são consultados em listar_atendimentos_ativos. Cancelamento na
        espera não cria registro aqui. Ordena apenas uma lista de apresentação.
        Para A atendimentos, B buckets e H encerrados: tempo
        O(B+A+H log(H+1)), espaço O(A+H), inclusive no pior caso.
        """
        encerrados = [a for a in self._atendimentos.listar_valores()
                      if a.situacao != SituacaoAtendimento.EM_ATENDIMENTO]
        return sorted(encerrados, key=lambda a: a.chave_inicio)

    @sincronizado
    def listar_chegadas(self) -> list[Paciente]:
        """Todos os estados por (chegada, ID), preservando referências.

        Para P pacientes e B buckets: tempo O(B+P log(P+1)), espaço O(P).
        Ordenação auxiliar de apresentação; a fila atual continua na árvore.
        """
        return sorted(self.listar_pacientes(), key=lambda p: p.chave_chegada)

    @sincronizado
    def obter_indicadores(self) -> dict:
        """Agregação nova a cada consulta, sem caches ou contadores adicionais.

        Dicionários de estados (tamanho fixo), campos e linhas por médico são
        exclusivamente saída de apresentação; não são índices por ID. A lista
        por médico não tem ordem garantida e inclui médicos com zero conclusões.
        Usa o contador real da entidade, mantido pela operação de conclusão.
        Pacientes cancelados na espera contam somente nos estados de pacientes.

        Para P pacientes, M médicos, A atendimentos e B soma dos buckets das
        três Hashes: tempo O(B+P+M+A), espaço O(P+M+A), no pior caso também.
        Use o contexto leitura() para materializar os campos das referências.
        """
        pacientes = self.listar_pacientes()
        medicos = self.listar_medicos()
        atendimentos = self._atendimentos.listar_valores()
        por_paciente = {estado.value: 0 for estado in SituacaoPaciente}
        por_medico = {estado.value: 0 for estado in SituacaoMedico}
        por_atendimento = {estado.value: 0 for estado in SituacaoAtendimento}
        for paciente in pacientes:
            por_paciente[paciente.situacao.value] += 1
        for medico in medicos:
            por_medico[medico.situacao.value] += 1
        for atendimento in atendimentos:
            por_atendimento[atendimento.situacao.value] += 1
        return {
            "total_pacientes": len(pacientes),
            "pacientes_por_estado": por_paciente,
            "total_medicos": len(medicos),
            "medicos_por_estado": por_medico,
            "conclusoes_por_medico": [
                {"medico": medico, "total_concluidos": medico.total_concluidos}
                for medico in medicos
            ],
            "total_atendimentos": len(atendimentos),
            "atendimentos_por_estado": por_atendimento,
        }
