# SIGAE WEB

Projeto acadêmico de gerenciamento de atendimentos de emergência, desenvolvido
em Python com Django. A aplicação WEB é exigida pelo enunciado; Python e Django
são escolhas da equipe. A metodologia adotada é Extreme Programming (XP).
Utilize exclusivamente dados fictícios.

## Estado atual

Estão implementados:

- Entidade `Paciente`, com validações, estados, transições e chaves de ordenação.
- Tabela Hash própria, com encadeamento separado, remoção, atualização,
  redimensionamento e validação estrutural.
- Min-Heap binário próprio, configurável para pacientes ou médicos, com Hash
  própria de posições, atualização, remoção e validação.
- Árvore Rubro-Negra própria, com inserção, busca, remoção, balanceamento,
  percurso em ordem e validação.
- Seis protótipos navegáveis com dados fictícios estáticos e testes de interface.

Os protótipos apenas apresentam telas. Cadastro, consulta de registros, triagem,
chamada, conclusão e cancelamento não são executados: os controles de operação
estão desabilitados. As views aceitam somente GET e não acessam os índices.

Ainda serão implementados `Medico`, `Atendimento`, o serviço central e a integração
entre interface, estados e estruturas. O estado compartilhado, os locks e o
rollback estão documentados, mas não implementados. A revisão dos protótipos pela
equipe e a avaliação visual e com leitor de tela permanecem pendentes.

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
a estratégia de estado em memória prevista para a integração perderá os registros
a cada reinício. Atualmente, as telas sempre exibem o mesmo conjunto estático.

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
```

Verificações complementares:

```bash
python manage.py check
git diff --check
```

Na auditoria da versão `9aaaed4`, os 70 testes passaram: 16 de Paciente, 27 da
Hash, 12 do Heap, 10 da árvore e 5 de views. Esse resultado não comprova operações
integradas de atendimento nem substitui a revisão visual dos protótipos.

## Documentação

- [Escopo oficial](docs/escopo.md): requisitos obrigatórios, opcionais e entregáveis.
- [Arquitetura](docs/arquitetura.md): responsabilidades, contratos, estruturas e
  estratégia futura de estado em memória.
- [Protótipos](docs/prototipos.md): telas, fluxos, dados demonstrativos e limitações.
- [Contratos das estruturas](atendimentos/contratos.py): interfaces públicas.
