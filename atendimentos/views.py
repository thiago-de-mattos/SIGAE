from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import BuscaForm, MedicoForm, PacienteForm, ReclassificacaoForm, RISCOS
from .services.estado import obter_sistema
from .services.sistema_atendimento import SistemaIndisponivel


SITUACOES = {
    "aguardando": "Aguardando",
    "em_atendimento": "Em atendimento",
    "concluido": "Concluído",
    "cancelado": "Cancelado",
    "disponivel": "Disponível",
}


def dados_paciente(paciente):
    return {
        "id": paciente.id,
        "nome": paciente.nome,
        "chegada": paciente.chegada,
        "risco": RISCOS[paciente.prioridade],
        "situacao": SITUACOES[paciente.situacao],
    }


def dados_medico(medico):
    return {
        "id": medico.id,
        "nome": medico.nome,
        "registro": medico.registro,
        "situacao": SITUACOES[medico.situacao],
        "total": medico.total_concluidos,
        "ultima_atribuicao": medico.ultima_atribuicao,
    }


def dados_atendimento(atendimento):
    return {
        "id": atendimento.id,
        "paciente": dados_paciente(atendimento.paciente),
        "medico": dados_medico(atendimento.medico),
        "inicio": atendimento.inicio,
        "fim": atendimento.fim,
        "situacao": SITUACOES[atendimento.situacao],
    }


def contexto_busca(request, buscar, apresentar):
    busca = BuscaForm(request.GET if "id" in request.GET else None)
    resultado = None
    if busca.is_bound and busca.is_valid():
        registro = buscar(busca.cleaned_data["id"])
        if registro is None:
            busca.add_error("id", "Registro não encontrado.")
        else:
            resultado = apresentar(registro)
    return {"busca": busca, "resultado": resultado}


def contexto_modulo(request, sistema, modulo):
    if modulo == "pacientes":
        return {
            "cadastro": PacienteForm(prefix="cadastro"),
            "pacientes": [dados_paciente(p) for p in sistema.listar_chegadas()],
            **contexto_busca(request, sistema.buscar_paciente, dados_paciente),
        }
    if modulo == "medicos":
        return {
            "cadastro": MedicoForm(prefix="cadastro"),
            "medicos": [dados_medico(m) for m in sorted(sistema.listar_medicos(), key=lambda m: m.id)],
            **contexto_busca(request, sistema.buscar_medico, dados_medico),
        }
    if modulo == "triagem":
        paciente = sistema.consultar_proximo_paciente()
        medico = sistema.consultar_proximo_medico()
        return {
            "reclassificacao": ReclassificacaoForm(prefix="reclassificacao"),
            "fila": [dados_paciente(p) for p in sistema.listar_fila()],
            "proximo_paciente": dados_paciente(paciente) if paciente else None,
            "proximo_medico": dados_medico(medico) if medico else None,
            "riscos": RISCOS.values(),
        }
    if modulo == "atendimentos":
        ativos = sorted(sistema.listar_atendimentos_ativos(), key=lambda a: a.id)
        return {"ativos": [dados_atendimento(a) for a in ativos]}

    indicadores = sistema.obter_indicadores()
    contexto = {
        "estados_pacientes": [
            (SITUACOES[estado], total) for estado, total in indicadores["pacientes_por_estado"].items()
        ],
        "estados_medicos": [
            (SITUACOES[estado], total) for estado, total in indicadores["medicos_por_estado"].items()
        ],
        "medicos": [dados_medico(m) for m in sorted(sistema.listar_medicos(), key=lambda m: m.id)],
        "chegadas": [dados_paciente(p) for p in sistema.listar_chegadas()],
    }
    if modulo == "historico":
        contexto["historico"] = [dados_atendimento(a) for a in sistema.listar_historico()]
    return contexto


def erro_indisponivel(request, modulo):
    return render(request, "atendimentos/indisponivel.html", {"modulo": modulo}, status=503)


@require_GET
def pagina(request, modulo):
    try:
        sistema = obter_sistema()
        with sistema.leitura():
            contexto = contexto_modulo(request, sistema, modulo)
    except SistemaIndisponivel:
        return erro_indisponivel(request, modulo)
    return render(request, f"atendimentos/{modulo}.html", {**contexto, "modulo": modulo})


# Cada ação tem um formulário de entrada e uma operação pública do serviço.
ACOES = {
    ("pacientes", "cadastrar"): (PacienteForm, "cadastro", "cadastrar_paciente", "Paciente cadastrado."),
    ("pacientes", "cancelar"): (BuscaForm, None, "cancelar_paciente", "Paciente cancelado."),
    ("triagem", "reclassificar"): (
        ReclassificacaoForm, "reclassificacao", "reclassificar_paciente", "Classificação atualizada."
    ),
    ("triagem", "chamar"): (None, None, "chamar_proximo", "Atendimento iniciado."),
    ("medicos", "cadastrar"): (MedicoForm, "cadastro", "cadastrar_medico", "Médico cadastrado."),
    ("atendimentos", "concluir"): (BuscaForm, None, "concluir_atendimento", "Atendimento concluído."),
    ("atendimentos", "cancelar"): (BuscaForm, None, "cancelar_paciente", "Atendimento cancelado."),
}


@require_POST
def acao(request, modulo, comando):
    configuracao = ACOES.get((modulo, comando))
    if configuracao is None:
        raise Http404
    formulario, chave, operacao, sucesso = configuracao
    form = formulario(request.POST, prefix=chave) if formulario else None
    erro = None

    try:
        sistema = obter_sistema()
        with sistema.leitura():
            if form is None or form.is_valid():
                try:
                    getattr(sistema, operacao)(**(form.cleaned_data if form else {}))
                except KeyError:
                    erro = "Registro não encontrado."
                except ValueError as exc:
                    erro = str(exc)
                else:
                    messages.success(request, sucesso)
                    destino = "atendimentos" if comando == "chamar" else modulo
                    return redirect(f"atendimentos:{destino}")
            contexto = contexto_modulo(request, sistema, modulo)
    except (SistemaIndisponivel, ExceptionGroup):
        return erro_indisponivel(request, modulo)

    if chave and form is not None:
        if erro:
            form.add_error(None, erro)
        contexto[chave] = form
    elif form is not None and not form.is_valid():
        erro = "Informe um ID válido."
    contexto.update(modulo=modulo, erro_acao=erro)
    return render(request, f"atendimentos/{modulo}.html", contexto, status=400)
