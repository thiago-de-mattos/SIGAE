# SIGAE WEB

Simulador acadêmico de gerenciamento de atendimentos de emergência, em Python
e Django. O sistema organiza a triagem, distribui pacientes entre médicos e
mantém histórico e indicadores. Utilize exclusivamente dados fictícios.

## Executar localmente

Pré-requisitos: Python 3.12 ou superior, Git e um navegador. A partir da pasta
que contém `manage.py`, crie um ambiente virtual e instale as dependências.

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py runserver --noreload
```

**Linux ou macOS**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py runserver --noreload
```

Abra [SIGAE WEB](http://127.0.0.1:8000/). Comece cadastrando médicos e pacientes.
A página de Triagem/Fila mostra o próximo paciente e o médico elegível. Após
chamar, use Atendimentos para concluir ou cancelar e confira o resultado no
Histórico.

| URL | Tela |
| --- | --- |
| `/` | Painel geral e indicadores |
| `/pacientes/` | Cadastro, consulta por ID e cancelamento |
| `/triagem/` | Fila, reclassificação e chamada |
| `/medicos/` | Cadastro, consulta e disponibilidade |
| `/atendimentos/` | Atendimento ativo, conclusão e cancelamento |
| `/historico/` | Encerramentos, conclusões por médico e chegadas |

O estado é compartilhado entre usuários no mesmo processo. Os registros
começam vazios e são perdidos no reinício. Use um único processo com
`--noreload`. SQLite é usado pelos componentes administrativos do Django.
Para usar `/admin/`, execute `manage.py migrate` e `manage.py createsuperuser`.
O simulador funciona localmente sem executar essas duas etapas.

## Verificação

No ambiente virtual:

```text
python manage.py check
python manage.py test
```

Para repetir somente a validação integrada da interface:

```text
python manage.py test atendimentos.tests.test_fluxo_web
```

- [Histórias de usuário](docs/historias.md)
- [Planejamento XP](docs/planejamento-xp.md)
- [Relatório técnico, evidências e roteiro para a defesa](docs/entrega.md)
- [Arquitetura](docs/arquitetura.md)
- [Escopo acadêmico](docs/escopo.md)
