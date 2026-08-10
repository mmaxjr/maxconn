# MAXCONN

[![PyPI](https://img.shields.io/pypi/v/maxconn.svg)](https://pypi.org/project/maxconn/)
[![Python](https://img.shields.io/pypi/pyversions/maxconn.svg)](https://pypi.org/project/maxconn/)
[![CI](https://github.com/mmaxjr/maxconn/actions/workflows/ci.yml/badge.svg)](https://github.com/mmaxjr/maxconn/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Português

Projeto criado por Marcos Max para ser uma biblioteca Python voltada a redes e
infraestrutura.

A ideia do MAXCONN é juntar, aos poucos, as ferramentas que um engenheiro de
redes ou DevOps usa no dia a dia para automatizar tarefas de rede: conexão em
equipamentos, execução de comandos, leitura de saída, coleta de dados,
validação, inventário e, mais adiante, módulos específicos para fornecedores.

O início do projeto é a camada de conexão. Hoje o MAXCONN já tem cliente SSH e
Telnet feitos sobre sockets, sem usar Paramiko, Netmiko, Scrapli ou Telnetlib
como cliente em runtime.

Pacote no PyPI: https://pypi.org/project/maxconn/

Exemplo:

```python
import maxconn

with maxconn.connect(
    "192.0.2.10",
    protocol="ssh",
    username="admin",
    password="secret",
) as conn:
    result = conn.run("display version", prompt_markers=(">", "#"))
    print(result.text)
```

### Instalação

Instalação para desenvolvimento:

```bash
git clone https://github.com/mmaxjr/maxconn
cd maxconn
pip install -e ".[dev]"
pytest -v
ruff check src tests
```

Instalação para uso normal:

```bash
pip install maxconn
```

Para usar SSH:

```bash
pip install "maxconn[ssh]"
```

Telnet não puxa dependências extras. SSH usa `cryptography` pelo extra `ssh`.
Paramiko fica só nos testes, para subir um servidor SSH local e validar o
cliente do MAXCONN contra uma implementação independente.

Versão atual em desenvolvimento: `0.1.3`.

CLI básica:

```bash
maxconn --version
maxconn ping 192.0.2.1
maxconn scan 192.0.2.1 --ports 22,23,80,443
maxconn traceroute 8.8.8.8
maxconn mtr 8.8.8.8 --count 5
maxconn snmp get 192.0.2.1 1.3.6.1.2.1.1.5.0 --community public
maxconn snmp walk 192.0.2.1 1.3.6.1.2.1.1 --community public
maxconn ssh 192.0.2.10 --username admin --password secret --command "show version"
maxconn telnet 192.0.2.20 --username admin --password secret --command "show status"
```

### Uso Básico

Telnet:

```python
import maxconn

with maxconn.connect(
    "192.0.2.20",
    protocol="telnet",
    username="admin",
    password="secret",
) as conn:
    result = conn.run("show status", prompt_markers=(">", "#"))
    print(result.text)
```

SSH:

```python
import maxconn

with maxconn.connect(
    "192.0.2.30",
    protocol="ssh",
    username="admin",
    password="secret",
) as conn:
    result = conn.run("show version", prompt_markers=(">", "#"))
    print(result.text)
```

Para uso mais direto, `Connection.send()`, `Connection.recv()`,
`Connection.read_until()` e `Connection.send_command()` continuam disponíveis.

### Resultado de Comando

`Connection.run()` retorna um resultado com campos úteis:

```python
result = conn.run("display version", prompt_markers=(">", "#"))

print(result.command)
print(result.text)
print(result.bytes)
print(result.elapsed)
print(result.exit_status)
print(result.ok)
```

`result.ok` é verdadeiro quando `exit_status` é `None` ou `0`. Em sessões CLI
interativas, como Telnet e shell SSH, geralmente não existe status de saída,
então `None` é esperado.

### Expect

Para automação guiada por prompt, use `ExpectSession` diretamente:

```python
from maxconn.automation import ExpectSession, PromptProfile

expect = ExpectSession(conn, prompt_markers=PromptProfile.CISCO)
output = expect.run("show running-config", timeout=20.0)
```

`ExpectSession` faz o básico que uma CLI de equipamento costuma precisar:

- espera por prompts
- remove eco do comando
- responde paginação simples, como `--More--`
- inclui a saída parcial quando ocorre timeout
- responde confirmações simples, como `[Y/N]`

### Sessões e Ping

`SessionManager` controla conexões nomeadas:

```python
import maxconn

manager = maxconn.SessionManager(defaults={"protocol": "ssh", "username": "admin"})
conn = manager.connect("olt-01", "192.0.2.10", password="secret")
result = conn.run("display version", prompt_markers=(">", "#"))
manager.close_all()
```

Ping básico:

```python
import maxconn

result = maxconn.ping("192.0.2.1")
print(result.reachable)
```

Scanner TCP:

```python
import maxconn

for result in maxconn.scan("192.0.2.1", ports=[22, 23, 80, 443]):
    print(result.port, "open" if result.open else "closed")
```

Traceroute e mini MTR:

```python
import maxconn

trace = maxconn.traceroute("8.8.8.8")
for hop in trace.hops:
    print(hop.hop, hop.address)

report = maxconn.mtr("8.8.8.8", count=5)
print(report.loss_percent, report.avg)
```

### HTTP e FTP

HTTP/HTTPS básico:

```python
from maxconn.protocol.http import HTTPClient

response = HTTPClient(timeout=5.0).get("https://example.com")
print(response.status_code)
print(response.text)
```

FTP básico:

```python
from maxconn.protocol.ftp import FTPClient

with FTPClient.connect(
    "192.0.2.40",
    username="user",
    password="secret",
) as ftp:
    print(ftp.list())
    data = ftp.download("backup.cfg")
```

SNMP v2c básico:

```python
from maxconn.protocol.snmp import SNMPClient

snmp = SNMPClient("192.0.2.1", community="public")
hostname = snmp.get("1.3.6.1.2.1.1.5.0")
print(hostname.value)

for item in snmp.walk("1.3.6.1.2.1.1"):
    print(item.oid, item.value)
```

### Timeouts

`connect()` aceita timeouts separados:

```python
conn = maxconn.connect(
    "192.0.2.30",
    protocol="ssh",
    username="admin",
    password="secret",
    connect_timeout=5.0,
    auth_timeout=10.0,
    command_timeout=5.0,
    prompt_timeout=10.0,
)
```

O argumento antigo `timeout=` continua funcionando. Quando `connect_timeout` ou
`auth_timeout` não são informados, `timeout=` é usado como padrão.

### Logging

A execução de comandos registra eventos pelo logger `maxconn.audit`:

```python
import logging

logging.basicConfig(level=logging.INFO)
```

Trechos sensíveis com palavras como `password`, `secret`, `token` ou `key` são
redigidos antes de ir para o log.

### Erros

Use a hierarquia de exceções do projeto:

```python
import maxconn

try:
    with maxconn.connect(
        "192.0.2.30",
        protocol="ssh",
        username="admin",
        password="bad-password",
    ) as conn:
        print(conn.run("show status", prompt_markers=(">", "#")).text)
except maxconn.AuthenticationError:
    print("Login failed")
except maxconn.ConnectionTimeoutError:
    print("Connection timed out")
except maxconn.ProtocolError as exc:
    print(f"Protocol problem: {exc}")
except maxconn.MaxConnError as exc:
    print(f"maxconn error: {exc}")
```

### Direção do Projeto

- Não transformar o projeto em wrapper de Paramiko, Netmiko, Scrapli ou Telnetlib.
- Manter dependências opcionais atrás de extras.
- Deixar bytes crus disponíveis para quem precisa.
- Dar uma API simples para o caso comum.
- Testar com servidores locais de Telnet e SSH sempre que fizer sentido.
- Publicar novas versões no PyPI por tag, usando GitHub Actions e Trusted Publishing.

## English

Project created by Marcos Max as a Python library for networking and
infrastructure work.

MAXCONN is meant to grow into a practical toolkit for network engineers and
DevOps engineers who automate network tasks: connecting to devices, running
commands, reading output, collecting data, validating state, building inventory,
and later adding vendor-specific modules.

The project starts with the connection layer. Today MAXCONN has SSH and Telnet
clients built on top of sockets, without using Paramiko, Netmiko, Scrapli, or
Telnetlib as runtime clients.

Package on PyPI: https://pypi.org/project/maxconn/

Example:

```python
import maxconn

with maxconn.connect(
    "192.0.2.10",
    protocol="ssh",
    username="admin",
    password="secret",
) as conn:
    result = conn.run("display version", prompt_markers=(">", "#"))
    print(result.text)
```

### Installation

Development install:

```bash
git clone https://github.com/mmaxjr/maxconn
cd maxconn
pip install -e ".[dev]"
pytest -v
ruff check src tests
```

Regular install:

```bash
pip install maxconn
```

For SSH:

```bash
pip install "maxconn[ssh]"
```

Telnet does not pull extra runtime dependencies. SSH uses `cryptography` through
the `ssh` extra. Paramiko is test-only and is used to run a local SSH server for
integration tests.

Current development version: `0.1.3`.

Basic CLI:

```bash
maxconn --version
maxconn ping 192.0.2.1
maxconn scan 192.0.2.1 --ports 22,23,80,443
maxconn traceroute 8.8.8.8
maxconn mtr 8.8.8.8 --count 5
maxconn snmp get 192.0.2.1 1.3.6.1.2.1.1.5.0 --community public
maxconn snmp walk 192.0.2.1 1.3.6.1.2.1.1 --community public
maxconn ssh 192.0.2.10 --username admin --password secret --command "show version"
maxconn telnet 192.0.2.20 --username admin --password secret --command "show status"
```

### Basic Usage

Telnet:

```python
import maxconn

with maxconn.connect(
    "192.0.2.20",
    protocol="telnet",
    username="admin",
    password="secret",
) as conn:
    result = conn.run("show status", prompt_markers=(">", "#"))
    print(result.text)
```

SSH:

```python
import maxconn

with maxconn.connect(
    "192.0.2.30",
    protocol="ssh",
    username="admin",
    password="secret",
) as conn:
    result = conn.run("show version", prompt_markers=(">", "#"))
    print(result.text)
```

For lower-level use, `Connection.send()`, `Connection.recv()`,
`Connection.read_until()`, and `Connection.send_command()` are still available.

### Command Result

`Connection.run()` returns a result object:

```python
result = conn.run("display version", prompt_markers=(">", "#"))

print(result.command)
print(result.text)
print(result.bytes)
print(result.elapsed)
print(result.exit_status)
print(result.ok)
```

`result.ok` is true when `exit_status` is `None` or `0`. Interactive CLI
sessions, such as Telnet and shell-style SSH, usually do not provide an exit
status, so `None` is expected.

### Expect

For prompt-based automation, use `ExpectSession` directly:

```python
from maxconn.automation import ExpectSession, PromptProfile

expect = ExpectSession(conn, prompt_markers=PromptProfile.CISCO)
output = expect.run("show running-config", timeout=20.0)
```

`ExpectSession` handles the common parts of a network device CLI:

- waits for prompts
- strips command echo
- answers simple pagination markers such as `--More--`
- includes partial output in timeout errors
- answers simple confirmation prompts such as `[Y/N]`

### Sessions and Ping

`SessionManager` controls named connections:

```python
import maxconn

manager = maxconn.SessionManager(defaults={"protocol": "ssh", "username": "admin"})
conn = manager.connect("olt-01", "192.0.2.10", password="secret")
result = conn.run("display version", prompt_markers=(">", "#"))
manager.close_all()
```

Basic ping:

```python
import maxconn

result = maxconn.ping("192.0.2.1")
print(result.reachable)
```

TCP scan:

```python
import maxconn

for result in maxconn.scan("192.0.2.1", ports=[22, 23, 80, 443]):
    print(result.port, "open" if result.open else "closed")
```

Traceroute and mini MTR:

```python
import maxconn

trace = maxconn.traceroute("8.8.8.8")
for hop in trace.hops:
    print(hop.hop, hop.address)

report = maxconn.mtr("8.8.8.8", count=5)
print(report.loss_percent, report.avg)
```

### HTTP and FTP

Basic HTTP/HTTPS:

```python
from maxconn.protocol.http import HTTPClient

response = HTTPClient(timeout=5.0).get("https://example.com")
print(response.status_code)
print(response.text)
```

Basic FTP:

```python
from maxconn.protocol.ftp import FTPClient

with FTPClient.connect(
    "192.0.2.40",
    username="user",
    password="secret",
) as ftp:
    print(ftp.list())
    data = ftp.download("backup.cfg")
```

Basic SNMP v2c:

```python
from maxconn.protocol.snmp import SNMPClient

snmp = SNMPClient("192.0.2.1", community="public")
hostname = snmp.get("1.3.6.1.2.1.1.5.0")
print(hostname.value)

for item in snmp.walk("1.3.6.1.2.1.1"):
    print(item.oid, item.value)
```

### Timeouts

`connect()` accepts separate timeouts:

```python
conn = maxconn.connect(
    "192.0.2.30",
    protocol="ssh",
    username="admin",
    password="secret",
    connect_timeout=5.0,
    auth_timeout=10.0,
    command_timeout=5.0,
    prompt_timeout=10.0,
)
```

The older `timeout=` argument still works. When `connect_timeout` or
`auth_timeout` is not provided, `timeout=` is used as the default.

### Logging

Command execution writes audit events through the `maxconn.audit` logger:

```python
import logging

logging.basicConfig(level=logging.INFO)
```

Command fragments with words such as `password`, `secret`, `token`, or `key`
are redacted before logging.

### Errors

Use the project exception hierarchy:

```python
import maxconn

try:
    with maxconn.connect(
        "192.0.2.30",
        protocol="ssh",
        username="admin",
        password="bad-password",
    ) as conn:
        print(conn.run("show status", prompt_markers=(">", "#")).text)
except maxconn.AuthenticationError:
    print("Login failed")
except maxconn.ConnectionTimeoutError:
    print("Connection timed out")
except maxconn.ProtocolError as exc:
    print(f"Protocol problem: {exc}")
except maxconn.MaxConnError as exc:
    print(f"maxconn error: {exc}")
```

### Project Direction

- Do not turn the project into a wrapper around Paramiko, Netmiko, Scrapli, or Telnetlib.
- Keep optional dependencies behind extras.
- Keep raw bytes available for code that needs them.
- Keep the common API simple.
- Test against local Telnet and SSH servers when it makes sense.
- Publish new versions to PyPI by tag, using GitHub Actions and Trusted Publishing.
