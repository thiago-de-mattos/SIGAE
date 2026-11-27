# SIGAE-07 — Histórias de usuário

| História | Como | Quero | Para | Critérios de aceitação |
| --- | --- | --- | --- | --- |
| HU01 | Recepcionista | Registrar paciente com chegada e risco | Colocá-lo na fila | Nome obrigatório, chegada com fuso, risco de 1 a 5, ID automático e paciente Aguardando. Dados inválidos preservam a fila. |
| HU02 | Recepcionista | Consultar paciente pelo ID | Confirmar seus dados e sua situação | Exibir o registro encontrado, mesmo encerrado. Informar se o ID não existir. |
| HU03 | Profissional da triagem | Reclassificar paciente aguardando | Atualizar a ordem clínica | Preservar ID e chegada, sem duplicar. Na chamada, vence menor risco, depois chegada mais antiga e menor ID. |
| HU04 | Coordenador | Cadastrar e consultar médicos | Acompanhar disponibilidade e carga | Nome e registro fictício obrigatórios. ID automático, médico disponível e contador inicialmente zero. |
| HU05 | Profissional da triagem | Chamar o próximo paciente | Iniciar o atendimento com um médico disponível | Escolher o médico por menor total concluído, última atribuição mais antiga e menor ID. Sem médico, preservar a fila. Sem paciente, preservar a disponibilidade médica. |
| HU06 | Médico | Concluir um atendimento ativo | Liberar o médico e registrar a conclusão | Preservar vínculo e horário no histórico. Incrementar o contador uma vez, inclusive diante de tentativa repetida. |
| HU07 | Recepcionista | Cancelar paciente na espera ou em atendimento | Encerrar corretamente o fluxo | Remover da espera ou liberar o médico, conforme o estado, sem incrementar conclusões. Manter o cadastro consultável. |
| HU08 | Coordenador | Ver painel, histórico e chegadas | Acompanhar o movimento da unidade | Exibir contagens por situação, conclusões por médico e chegadas ordenadas por instante e ID. Distinguir atendimentos ativos de encerrados. |
