# SIGAE-24 — Relatório técnico e entrega

O SIGAE WEB mantém cadastros e atendimentos em memória e usa três tipos de estruturas
de dados próprias, com instâncias independentes dos Heaps de pacientes e médicos, para executar as operações. O roteiro abaixo pode ser
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

### Suíte permanente — 27/11/2026

Na branch `experiment/ux-ui-redesign`, `python manage.py test` passou com
**174 testes**; `python manage.py check` não apontou problemas e
`git diff --check` passou. Além das evidências acima, `test_interface` cobre
renderização dos seletores, valores após erros e marcação do preenchimento de
chegada; `test_fluxo_web` cobre cancelamento pela triagem, índices, próxima
chamada, CSRF, erros e destino interno de retorno. Esses testes não executam
JavaScript nem substituem validação interativa em navegador.

### Testes adicionais temporários da auditoria

Quatro testes executados somente em memória foram aprovados. Não foram
adicionados ao repositório e **não integram os 174 testes permanentes**:

| Cenário | Execução e resultado |
| --- | --- |
| Sequências aleatórias | Oito sementes, 300 passos cada (2.400 passos), combinando cadastro, reclassificação, chamada e encerramento; conferência de invariantes, vínculos, totais e mínimos com oráculos independentes. |
| Cadastro concorrente | 120 pacientes em até 12 threads; IDs únicos, referências preservadas e índices válidos. |
| Corrida de encerramento WEB | 30 disputas entre conclusão e cancelamento; uma resposta 302 e outra 400, um histórico e contador coerente em cada disputa. |
| Recuperação impossível | Falha injetada na inserção e na compensação; HTTP 503 nas seis telas e em nova chamada, impedindo uso de estado incerto. |

Os scripts temporários não foram persistidos; os resultados acima registram
esta execução e não são reproduzidos pelo comando da suíte permanente.

### Alcance e pendências

A comparação com `main` local encontrou entidades, estruturas, serviços,
formulários e dependências inalterados. A mudança de produção no backend é o
retorno do cancelamento à triagem na view. A revisão do código não encontrou
bibliotecas prontas substituindo os índices obrigatórios; coleções auxiliares
servem à apresentação, validação e recuperação.

A implementação visual e suas limitações estão descritas na
[arquitetura](arquitetura.md#interface-da-branch-experimental). A instalação
limpa, o comportamento JavaScript, o teclado e a responsividade em navegador
**não foram validados nesta auditoria**. O relato anterior de teste manual
referia-se à versão anterior ao redesign e não comprova a interface atual.
Os testes aprovados não demonstram ausência absoluta de defeitos; a validação
é limitada ao processo único em memória previsto pelo projeto.

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
O histórico de desenvolvimento registra os cartões SIGAE e a integração
anterior em `feature/24-entrega`. Esta revisão documenta o estado de trabalho
da branch `experiment/ux-ui-redesign`, incluindo alterações locais ainda não
commitadas; não representa uma publicação ou merge.
