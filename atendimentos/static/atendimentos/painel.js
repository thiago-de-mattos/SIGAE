/* Agregações de apresentação do snapshot recebido; não selecionam nem ordenam a fila. */
const painel = document.querySelector('.painel-operacoes');
if (painel) {
    const aguardando = painel.querySelectorAll('[data-pacientes-aguardando] [data-risco]');
    painel.querySelectorAll('[data-nivel]').forEach((linha) => {
        let total = 0;
        aguardando.forEach((paciente) => {
            if (paciente.dataset.risco === linha.dataset.nivel) total += 1;
        });
        linha.querySelector('.total-risco').textContent = `${total} paciente${total === 1 ? '' : 's'}`;
        linha.querySelector('.trilho-risco > span').style.width = `${aguardando.length ? total / aguardando.length * 100 : 0}%`;
    });
    painel.querySelector('[data-fila-vazia]').hidden = aguardando.length !== 0;
    painel.querySelector('.distribuicao-risco').hidden = false;

    // Escala relativa ao maior total concluído, apenas para comparar as barras.
    const conclusoes = painel.querySelectorAll('[data-conclusoes]');
    let maiorTotal = 0;
    conclusoes.forEach((linha) => {
        const total = Number(linha.dataset.conclusoes);
        if (total > maiorTotal) maiorTotal = total;
    });
    conclusoes.forEach((linha) => {
        const trilho = linha.querySelector('.trilho-conclusoes');
        trilho.firstElementChild.style.width = `${maiorTotal ? Number(linha.dataset.conclusoes) / maiorTotal * 100 : 0}%`;
        trilho.hidden = false;
    });
}
