/* Melhoria progressiva: os formulários continuam usando as rotas Django. */
// Inicializa uma única vez; nunca recalcula ao editar, focar ou enviar.
const chegada = document.querySelector('[data-chegada-atual] input[name="cadastro-chegada"]');
if (chegada && !chegada.value && !chegada.defaultValue
    && !chegada.validity.badInput && document.activeElement !== chegada) {
    const partes = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'America/Sao_Paulo',
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).formatToParts(new Date());
    const parte = (tipo) => partes.find((item) => item.type === tipo).value;
    chegada.value = `${parte('year')}-${parte('month')}-${parte('day')}T${parte('hour')}:${parte('minute')}`;
}

document.addEventListener('submit', (event) => {
    const mensagem = event.target.dataset.confirmar;
    if (mensagem && !window.confirm(mensagem)) {
        event.preventDefault();
    }
});

// Leva o teclado ao primeiro campo inválido após a validação do servidor.
const campoInvalido = document.querySelector('[aria-invalid="true"]');
if (campoInvalido) campoInvalido.focus();
