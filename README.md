# SIGAE WEB

Projeto acadêmico de gerenciamento de atendimentos de emergência, desenvolvido
em Python com Django. A aplicação WEB é exigida pelo enunciado; Python e Django
são escolhas da equipe. A metodologia adotada é Extreme Programming (XP).
Utilize exclusivamente dados fictícios.

## Estado atual

Estão implementados:

- Entidades `Paciente`, `Medico` e `Atendimento`, com validações, estados,
  transições e preservação de referências.
- Tabela Hash própria, com encadeamento separado, remoção, atualização,
  redimensionamento e validação estrutural.
- Min-Heap binário próprio, configurável para pacientes ou médicos, com Hash
  própria de posições, atualização, remoção e validação.
- Árvore Rubro-Negra própria, com inserção, busca, remoção, balanceamento,
  percurso em ordem e validação.
- Serviço `SistemaAtendimento` em memória, com IDs independentes por entidade,
  cadastro, consultas, triagem pela prioridade no cadastro, reclassificação,
  chamada e distribuição médica, conclusão, cancelamento, históricos e indicadores.
  Coordena as estruturas próprias e preserva as referências compartilhadas.
- Seis protótipos navegáveis com dados fictícios estáticos e testes de interface.

Os protótipos apenas apresentam telas. Cadastro, consulta de registros, triagem,
chamada, conclusão e cancelamento não são executados pela interface: os controles de operação
estão desabilitados. As views aceitam somente GET e não acessam os índices.

O serviço está implementado para execução sequencial em memória, com compensação
local em cadastros, reclassificação, chamada e encerramentos. Falhas de recuperação
são propagadas explicitamente; ainda não tornam o serviço indisponível.

A SIGAE-20 tratará a instância compartilhada entre requisições, concorrência,
locks, rollback centralizado e indisponibilidade após falha de recuperação.
A integração WEB e a revisão dos protótipos pela equipe, incluindo avaliação
visual e com leitor de tela, permanecem pendentes.

## Pré-requisitos

- Python 3.12 ou superior, com `pip` e suporte a `venv`.
- Git, para obter o repositório, e um navegador para visualizar os protótipos.
- Acesso a um índice de pacotes que disponibilize as versões de `requirements.txt`.

O ambiente local utilizado na verificação possui Python 3.14.4 e Django 6.1.3.
O requisito mínimo de Python foi conferido nos metadados das dependências
instaladas; outras versões de Python não foram testadas nesta revisão.

As dependências fixadas são Django 6.1.3, asgiref 3.13.0, sqlparse 0.6.1 e
tzdata 2026.6. `requirements.txt` é a referência para instalação. Não são
necessários Node.js, bibliotecas de interface ou um servidor de banco externo.

## Instalação e ambiente virtual

Obtenha o repositório e entre na raiz do projeto:

```bash
git clone https://github.com/thiago-de-mattos/SIGAE.git
cd SIGAE
```

Em Linux ou macOS, utilizando um interpretador compatível:

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

No Windows, com PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

O exemplo Windows seleciona Python 3.14, que deve estar instalado. Se a ativação
não estiver disponível, execute os comandos seguintes com
`.venv/bin/python` em Linux/macOS ou `.\.venv\Scripts\python.exe` no Windows.
Todos os comandos devem ser executados na pasta que contém `manage.py`.

## Configuração local

O projeto utiliza `config/settings.py`; não há arquivo `.env` obrigatório ou
variáveis de ambiente específicas exigidas para os protótipos.

- Idioma: `pt-br`; fuso: `America/Sao_Paulo`, com `USE_TZ = True`.
- Templates em `templates/atendimentos/` e CSS em `css/`, servido pelo Django
  durante o desenvolvimento.
- SQLite configurado em `db.sqlite3` para os componentes padrão do Django.
  Os protótipos e as estruturas próprias não usam esse banco para os registros
  de pacientes, médicos ou atendimentos.
- `DEBUG = True`, chave de desenvolvimento e configuração de hosts local.
  Esta configuração destina-se ao desenvolvimento, não à publicação em produção.

Para preparar as tabelas dos componentes padrão do Django e verificar a configuração:

```bash
python manage.py migrate
python manage.py check
```

As migrações não implementam persistência das estruturas próprias. As telas
estáticas e os testes atuais não dependem de dados cadastrados no banco.

## Execução e URLs

```bash
python manage.py runserver --noreload
```

Abra `http://127.0.0.1:8000/`. A opção `--noreload` evita reinícios automáticos;
os registros do serviço em memória são perdidos a cada reinício. O serviço ainda
não é compartilhado entre requisições nem acessado pelas views. Atualmente, as telas sempre exibem o mesmo conjunto estático.

| URL | Tela |
| --- | --- |
| `/` | Painel geral |
| `/pacientes/` | Pacientes |
| `/triagem/` | Triagem/Fila |
| `/medicos/` | Médicos |
| `/atendimentos/` | Atendimentos |
| `/historico/` | Histórico |

A rota `/admin/` também está configurada pelo Django, mas não é um módulo de
atendimento nem oferece gerenciamento das estruturas próprias. Seu acesso requer
as migrações e uma conta administrativa, criada com `python manage.py createsuperuser`.

## Testes e verificações

Execute a suíte completa:

```bash
python manage.py test
```

Para executar os testes por módulo:

```bash
python manage.py test atendimentos.tests.test_paciente
python manage.py test atendimentos.tests.test_tabela_hash
python manage.py test atendimentos.tests.test_min_heap
python manage.py test atendimentos.tests.test_arvore_rubro_negra
python manage.py test atendimentos.tests.test_views
python manage.py test atendimentos.tests.test_medico
python manage.py test atendimentos.tests.test_atendimento
python manage.py test atendimentos.tests.test_sistema_atendimento
python manage.py test atendimentos.tests.test_cadastros
python manage.py test atendimentos.tests.test_reclassificacao
python manage.py test atendimentos.tests.test_chamada
python manage.py test atendimentos.tests.test_encerramento
python manage.py test atendimentos.tests.test_indicadores
python manage.py test atendimentos.tests.test_integracao_servico
```

Verificações complementares:

```bash
python manage.py check
git diff --check
```

Na conclusão da SIGAE-19, os 160 testes foram aprovados: entidades, estruturas,
serviço e protótipos WEB. A SIGAE-19.9 acrescentou três cenários integrados aos
157 testes anteriores, verificando fluxo completo, distribuição, referências,
invariantes, colisões, redimensionamentos e recuperação de falhas. Esse resultado
não comprova concorrência nem integração WEB e não substitui a revisão visual.

## Documentação

- [Escopo oficial](docs/escopo.md): requisitos obrigatórios, opcionais e entregáveis.
- [Arquitetura](docs/arquitetura.md): responsabilidades, contratos, estruturas e
  serviço em memória e estratégia futura de compartilhamento entre requisições.
- [Protótipos](docs/prototipos.md): telas, fluxos, dados demonstrativos e limitações.
- [Contratos das estruturas](atendimentos/contratos.py): interfaces públicas.
