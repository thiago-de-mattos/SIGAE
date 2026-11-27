# SIGAE-12 — Protótipos navegáveis

Referências: [escopo oficial](escopo.md) e [arquitetura](arquitetura.md).
Esta entrega representa a interface; não implementa operações de negócio.

## Visualização e telas

Com o ambiente existente, executar `python manage.py runserver --noreload`.
Abrir as URLs abaixo em `http://127.0.0.1:8000`. Não requer novas dependências.

| URL | Tela | Conteúdo representado |
| --- | --- | --- |
| `/` | Painel geral | Pacientes por estado, disponibilidade, atendimentos por médico separados em concluídos/cancelados/ativos e chegadas cronológicas. |
| `/pacientes/` | Pacientes | Cadastro com ID automático previsto, nome, chegada, risco, estado; consulta por ID, listagem e cancelamento. |
| `/triagem/` | Triagem/Fila | Cinco riscos numerados e nomeados, ordem clínica, triagem, reclassificação e chamada automática com critérios de seleção médica. |
| `/medicos/` | Médicos | Cadastro e consulta, ID automático previsto, nome, registro fictício, disponibilidade, conclusões e última atribuição. |
| `/atendimentos/` | Atendimentos | ID, paciente, médico vinculado, status, início, conclusão e cancelamento. |
| `/historico/` | Histórico | Vínculos preservados, início/fim, conclusões e cancelamentos, totais por médico. |

Todas as telas incluem navegação persistente com página atual indicada, aviso
explícito de demonstração e exemplos expansíveis de estado vazio e mensagens de
erro. Os exemplos não são respostas a operações. Não há mensagens de sucesso.

## Fluxos representados

- Painel → Pacientes → Triagem/Fila: cadastro e consulta previstos, seleção do risco
  e reclassificação de pacientes Aguardando, preservando ID e chegada.
- Triagem/Fila → Médicos: consultar disponibilidade. Chamada futura seleciona
  paciente por prioridade, chegada e ID; médico por conclusões, tempo desde a
  última atribuição e ID. Sem médico, preservar a fila; sem paciente, não chamar.
- Atendimentos → Histórico: conclusão incrementa uma vez o contador e libera o
  médico; cancelamento anterior à conclusão libera sem incrementar. Encerramentos
  repetidos são proibidos. Nenhum desses passos é executado pelo protótipo.
- Histórico → Pacientes: visualizar todos os estados. Cancelamento na espera
  permanece no cadastro e não cria um atendimento fictício.

A navegação entre módulos funciona por links GET. Os botões de operação e campos
estão desabilitados. As views apenas renderizam templates e rejeitam métodos
HTTP diferentes de GET; não leem formulários nem parâmetros como comandos.

## Dados demonstrativos e coerência

Retrato fixo de 26/11/2026 às 09:30, UTC−03:00. Há seis pacientes: três Aguardando,
um Em atendimento, um Concluído e um Cancelado. Dos três médicos, dois estão
Disponíveis e um Em atendimento. Há uma conclusão, um cancelamento e um
atendimento ativo. Todos os nomes e registros são fictícios. Os indicadores
são texto estático coerente com as tabelas, não cálculos do serviço.

Os riscos são 1 Emergência, 2 Muito urgente, 3 Urgente, 4 Pouco urgente e
5 Não urgente. Cor é apenas complementar ao número e ao texto.

## Acessibilidade e responsividade

Idioma português, títulos por tela, link para pular ao conteúdo, navegação com
`aria-current`, foco visível, campos rotulados, tabelas com captions e cabeçalhos,
regiões de tabela focáveis com rolagem horizontal em telas pequenas. Os exemplos
usam `details/summary` nativos acessíveis por teclado. Layout adapta navegação e
cartões ao espaço disponível. Não foram adicionados JavaScript, fontes externas
ou bibliotecas. Verificação visual em navegador e avaliação com leitor de tela
permanecem pendentes; testes de templates não comprovam esses aspectos.

## Limitações e revisão

- Sem cadastro real, busca real, chamada, reclassificação, encerramento, geração
  de IDs, atualização de contadores, persistência ou estado compartilhado.
- Sem acesso a entidades, estruturas ou serviços. Na integração futura, views
  deverão chamar o serviço central, conforme a arquitetura, sem manipular índices.
- Estados vazios e erros são exemplos alternativos, não condições atuais.
- Os testes verificam renderização, navegação, aviso de demonstração e rejeição
  de métodos de alteração; não comprovam funcionalidades de atendimento.
- Revisão pela equipe: **pendente**. Validar campos, fluxos, textos, navegação,
  responsividade e acessibilidade antes de considerar o protótipo revisado.
