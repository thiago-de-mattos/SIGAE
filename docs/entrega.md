# SIGAE-24 — Relatório técnico e entrega

O SIGAE WEB mantém cadastros e atendimentos em memória e usa três estruturas
de dados próprias para executar as operações. O roteiro abaixo pode ser
repetido após a instalação indicada no [README](../README.md).

## Decisões de implementação

| Estrutura | Uso | Operações e custo |
| --- | --- | --- |
| Tabela Hash com encadeamento | Localizar pacientes, médicos e atendimentos por ID. Também indexa posições dentro de cada Heap. | Busca esperada O(1), pior caso O(n) com colisões. Redimensiona para manter a taxa de ocupação. |
| Árvore Rubro-Negra | Manter pacientes em espera por instante de chegada e ID. | Inserção e remoção O(log n) com rotações e recolorações. Listagem da fila em O(n) por percurso em ordem. |
| Min-Heap de pacientes | Selecionar pela tupla de prioridade, instante de chegada e ID. | Mínimo O(1). Inserções, remoções e reclassificações O(log n) esperado amortizado com a Hash de posições. |
| Min-Heap de médicos | Selecionar disponíveis por total concluído, última atribuição e ID. | Mínimo O(1). Chamada remove o médico e o encerramento o reinsere com a nova chave. |

As estruturas guardam referências às entidades do serviço. Pacientes
aguardando estão no Heap e na árvore. Médicos ocupados ficam fora do Heap
de disponíveis. Cancelar preserva o cadastro e libera o médico de um
atendimento ativo sem alterar seu total de conclusões.

O serviço usa um lock reentrante para serializar operações e leituras
compostas. O rollback executa compensações em ordem inversa e verifica índices,
estados, vínculos ativos e contagens. Se falhar, o processo bloqueia as
operações de negócio e a interface responde com HTTP 503. IDs reservados podem
deixar lacunas. As views materializam os campos sob o lock e renderizam depois.
O sistema começa vazio a cada reinício e foi projetado para um único processo.

## Evidências

| Histórias | Evidência reproduzível |
| --- | --- |
| HU01–HU03 | `test_paciente`, `test_reclassificacao` e `test_fluxo_web` verificam validação, busca por ID, mudança de risco e ordem de chamada. |
| HU04–HU05 | `test_chamada` e `test_fluxo_web` verificam desempates, três médicos, indisponibilidade e chamadas simultâneas. |
| HU06–HU08 | `test_encerramento`, `test_indicadores` e `test_fluxo_web` verificam encerramentos, repetição, contadores e histórico. |
| Estruturas e rollback | `test_tabela_hash`, `test_min_heap`, `test_arvore_rubro_negra` e `test_integracao_servico` verificam colisões, redimensionamento, invariantes e falhas injetadas. |

A suíte completa passou com **164 testes**. O fluxo manual no navegador
registrou um médico e um paciente fictícios, reclassificou o risco, iniciou
e concluiu o atendimento. O histórico exibiu o vínculo e uma conclusão para
o médico. A revisão cega exercitou clientes independentes e verificou que
um único pedido concorrente iniciou ou concluiu o mesmo atendimento.

## Roteiro de defesa

1. Cadastre os médicos Alfa, Beta e Gama, com registros fictícios. Cadastre
   quatro pacientes com riscos 5, 2, 2 e 3. Use o mesmo horário para os dois
   pacientes de risco 2.
2. Reclassifique o último paciente para risco 1. Faça três chamadas. Ele
   deve sair primeiro, seguido pelos dois de risco 2 em ordem de ID. Cada
   médico recebe um paciente pela ordem de ID, pois está no primeiro turno.
3. Com todos ocupados, confira que o quarto paciente permanece na fila.
   Conclua o atendimento de Alfa e cancele o de Beta. Faça nova chamada e
   confira que Beta recebe o quarto paciente, pois tem menos conclusões.
4. Confira as situações no Painel e os vínculos no Histórico. Execute
   `python manage.py test atendimentos.tests.test_tabela_hash atendimentos.tests.test_arvore_rubro_negra`
   para demonstrar colisões, redimensionamento, inserções e remoções.
5. Na defesa, cada integrante explica a estrutura em que trabalhou e a
   participação nas duplas. Os nomes, datas e a retrospectiva real do grupo
   dependem do registro dos integrantes.

O [planejamento XP](planejamento-xp.md) registra iterações e estimativas.
O histórico de Git identifica os oito cartões pelos IDs SIGAE. As branches
foram encadeadas na ordem do Trello. A última, `feature/24-entrega`, reúne
o fluxo completo.
