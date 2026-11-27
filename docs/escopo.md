# SIGAE-01 — Escopo oficial do SIGAE WEB

Este documento é a referência oficial dos requisitos e critérios de entrega do
projeto, conforme o enunciado SIGAE WEB. Define o que deve ser entregue, sem
afirmar que as funcionalidades já estão implementadas. O próprio enunciado exige
uma aplicação WEB; essa exigência não decorre de autorização excepcional do
professor.

As responsabilidades e a organização existentes em [arquitetura.md](arquitetura.md)
permanecem válidas. As interfaces das estruturas estão em
[contratos.py](../atendimentos/contratos.py). Este escopo não altera esses contratos.

## Requisitos obrigatórios

### Plataforma e dados

- Entregar aplicação WEB, conforme exigência do enunciado. Python e Django são
  escolhas da equipe para a implementação, preservando a arquitetura existente.
- Utilizar exclusivamente dados fictícios, inclusive nomes e registros médicos.
- Pacientes: ID automático e único, nome, instante de chegada, risco inteiro de
  1 a 5 e estado Aguardando, Em atendimento, Concluído ou Cancelado.
  Os riscos são: 1 Emergência, 2 Muito urgente, 3 Urgente, 4 Pouco urgente
  e 5 Não urgente.
  O campo `prioridade` representa o risco; menor valor tem precedência clínica.
- Médicos: ID automático e único, nome, registro fictício, disponibilidade e
  contador de atendimentos concluídos. Registrar a última atribuição de paciente
  para resolver os desempates da distribuição.

### Estruturas próprias

| Estrutura obrigatória | Conteúdo, chave e comportamento |
| --- | --- |
| Árvore Rubro-Negra | Pacientes em espera, com chave `(chegada, ID)`; inserção, remoção, busca e percurso em ordem. Implementar rotações, recoloração e correções que preservem as propriedades rubro-negras. |
| Min-Heap de pacientes | Pacientes em espera, com chave `(prioridade, chegada, ID)`; selecionar o menor elemento e reorganizar após reclassificação, sem duplicar pacientes. |
| Min-Heap de médicos | Médicos disponíveis; selecionar o menor número de atendimentos concluídos, depois o maior tempo sem receber paciente e, por fim, o menor ID. |
| Tabela Hash de pacientes | Índice por ID, com função de dispersão, tratamento de colisões, inserção, consulta, remoção e redimensionamento com redistribuição dos registros. |

Para médicos, a chave definida na arquitetura é
`(total_concluidos, ultima_atribuicao_ou_minimo, ID)`: uma atribuição mais antiga
vence entre contadores iguais. Médicos nunca atribuídos precedem os já atribuídos
em empate de conclusões; entre nunca atribuídos, vence o menor ID. Essa convenção
de inicialização é uma decisão do projeto registrada na arquitetura.

É proibido substituir as estruturas obrigatórias por `dict`, `heapq`, `Map` ou
bibliotecas prontas. Recursos auxiliares devem ter finalidade e justificativa
documentadas, sem assumir o papel dos índices obrigatórios. Na arquitetura atual,
listas armazenam posições do Heap e buckets da Hash, e uma Hash própria mantém
as posições por ID do Heap. Listagens auxiliares servem à apresentação; ordenar
uma lista histórica é justificável porque a árvore contém apenas a espera, mas
não substitui seu percurso nem a seleção pelo Heap.

### Operações e distribuição

- Disponibilizar cadastro e consulta de pacientes e médicos, triagem,
  reclassificação, chamada, atendimento, conclusão, cancelamento e histórico.
- A triagem define o risco; a reclassificação de paciente Aguardando atualiza
  sua prioridade e reorganiza o Heap sem duplicação, preservando ID e chegada.
- Na chamada, selecionar automaticamente o paciente pela prioridade clínica e
  o médico disponível pelo critério do Heap de médicos. A distribuição entre
  médicos não pode alterar a ordem clínica dos pacientes.
- Sem médico disponível, preservar integralmente a fila de pacientes. Sem
  paciente elegível, não criar atendimento nem ocupar médico.
- Uma chamada bem-sucedida retira o paciente dos índices de espera, ocupa o
  médico e cria o atendimento com os vínculos correspondentes.
- Concluir um atendimento incrementa exatamente uma vez o contador do médico,
  conclui o paciente e libera o médico para nova seleção.
- Cancelar antes da conclusão não incrementa o contador. Se o paciente estiver
  aguardando, removê-lo dos índices de espera; se estiver em atendimento,
  encerrar o vínculo ativo e liberar o médico. Preservar os registros históricos.
- Rejeitar transições inválidas e encerramentos repetidos sem alterar o estado.

### Consistência

- Hash de pacientes conserva o cadastro de todos os estados; árvore e Heap de
  pacientes contêm exatamente os pacientes Aguardando.
- Heap de médicos contém exatamente os médicos disponíveis.
- Compartilhar referências às mesmas entidades entre índices, sem cópias
  independentes, IDs duplicados ou referências órfãs.
- Cada paciente e médico participa de no máximo um atendimento ativo. Um
  atendimento ativo referencia entidades existentes e Em atendimento.
- O contador de cada médico corresponde apenas às conclusões, excluindo
  cancelamentos. Conclusão e cancelamento preservam a última atribuição.
  Preservar esse contador durante toda a sessão do sistema, inclusive entre
  requisições; se houver persistência, conservá-lo também ao restaurar o estado.
- Coordenar alterações de índices, estados e vínculos como uma operação
  consistente, inclusive diante de falhas e chamadas concorrentes.
- Preservar o histórico e as associações de atendimentos encerrados; cancelamentos
  na espera permanecem identificáveis no cadastro, sem inventar atendimento.

### Interface e indicadores

A interface WEB deve oferecer as áreas Painel geral, Pacientes, Triagem/Fila,
Médicos, Atendimentos e Histórico, com acesso às operações correspondentes e
mensagens de validação compreensíveis.

Cada atendimento deve apresentar o paciente, o médico vinculado, o status
e o horário de início.

Apresentar atendimentos por médico, pacientes por estado e chegadas em ordem
cronológica. Distinguir conclusões de cancelamentos nos totais por médico.
A fila cronológica usa o percurso da árvore; a listagem de chegadas de todos
os estados pode usar a ordenação auxiliar prevista na arquitetura.

### Testes e critérios de aceite

Os testes devem comprovar os comportamentos, não apenas a existência de classes
ou assinaturas. Registrar cenários, resultados esperados e evidências de execução.

| Cenário obrigatório | Resultado a verificar |
| --- | --- |
| Distribuição entre três médicos inicialmente zerados | Com todos disponíveis e nunca atribuídos, as chamadas ocupam médicos distintos, por menor ID nos empates; após conclusões e liberação, novas chamadas respeitam carga e tempo desde a última atribuição. |
| Menor carga | Entre médicos disponíveis, vence quem tem menos conclusões, mesmo que outro esteja há mais tempo sem receber paciente. |
| Desempates | Para médicos, comparar última atribuição e depois ID; para pacientes com mesma prioridade, comparar chegada e depois ID. |
| Indisponibilidade | Médico ocupado não recebe outro paciente; sem médico disponível, chamada preserva pacientes, ordem, estados e vínculos da fila. |
| Prioridade clínica e reclassificação | Menor risco numérico é chamado primeiro; mudar risco reorganiza a fila sem duplicação e sem alterar a chave cronológica. |
| Colisões na Hash | IDs que colidem continuam inseríveis, consultáveis e removíveis sem perda de outros registros. |
| Redimensionamento da Hash | Após redistribuição, todos os registros restantes continuam acessíveis e a quantidade está correta. |
| Balanceamento da Rubro-Negra | Inserções e remoções que exigem rotações e recoloração preservam ordenação, raiz preta, ausência de pai e filho vermelhos e mesma altura negra nos caminhos até NIL. |
| Consistência após alterações | Cadastro, chamada, reclassificação, conclusão, cancelamento e tentativas inválidas preservam os invariantes dos índices, estados, contadores e vínculos; falhas intermediárias não deixam alterações parciais. |

### Entrega e defesa prática

- Entregar código-fonte e aplicação WEB funcional.
- Fornecer README reproduzível com pré-requisitos, instalação, configuração,
  execução da aplicação e execução dos testes.
- Entregar relatório técnico curto, explicando estruturas, algoritmos, decisões
  e justificativas dos recursos auxiliares, acompanhado de evidências de testes.
- Realizar defesa prática com operações reais na aplicação usando dados fictícios.
  Cada integrante deve explicar as estruturas, seus critérios e sua participação
  nas operações demonstradas.

## Melhorias opcionais e decisões do projeto

- Visualização gráfica das estruturas é opcional; não condiciona o aceite.
- Persistência em banco de dados é opcional. Manter o estado necessário entre
  requisições continua necessário para o funcionamento; a solução segue a
  definição arquitetural da SIGAE-10, sem exigir banco.
- Hash de médicos é opcional no enunciado, embora já escolhida na arquitetura.
  Hash de atendimentos e Hash interna de posições dos Heaps também são decisões
  arquiteturais existentes, não novas exigências do enunciado.
- Capacidade inicial 11, fator de carga 0,75, dispersão por módulo, encadeamento
  separado e sentinelas são escolhas de implementação documentadas na arquitetura,
  não parâmetros obrigatórios impostos pelo enunciado.

Essas distinções preservam a arquitetura: domínio e estruturas independem do
Django; o serviço central coordena as operações e os índices; views recebem
requisições e apresentam os resultados sem alterar diretamente as entidades.

## Confronto com a documentação existente

- Na revisão de 27/11/2026, o README contém pré-requisitos, instalação, execução,
  os seis módulos e comandos de verificação. Os critérios dos dois Heaps e as
  demais decisões técnicas estão na arquitetura e no relatório de entrega.
  Isso corrige a observação inicial de ausência dessas instruções; a instalação
  limpa permanece não verificada nesta auditoria.
- A arquitetura inclui Hash de médicos como decisão do projeto; sua presença
  não torna essa estrutura obrigatória no enunciado. O mesmo cuidado vale para
  a Hash de atendimentos e os parâmetros concretos de implementação.
- A arquitetura e os contratos são compatíveis com as chaves, operações e
  invariantes deste escopo. Rotações, recoloração, dispersão e redimensionamento
  são detalhes internos e não precisam virar novos métodos públicos dos Protocols.
- A arquitetura distingue componentes existentes de planejados. Os Protocols
  não implementam algoritmos e não comprovam os testes; este documento também
  não declara concluídas as funcionalidades futuras.
- Persistência e visualização gráfica continuam opcionais. A arquitetura
  documenta o processo único em memória e a perda do estado ao reiniciar.

A SIGAE-01 entrega somente este documento; não implementa funcionalidades nem
altera outros arquivos.

A revisão documental da branch experimental não altera os requisitos acima.
Redesign e cancelamento pela Triagem/Fila reutilizam as operações existentes.
As evidências atuais, incluindo a distinção entre suíte permanente e testes
adicionais temporários, estão em [entrega.md](entrega.md#evidências).
