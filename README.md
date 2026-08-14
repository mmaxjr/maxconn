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

Versão atual em desenvolvimento: `0.1.19`.

### Status dos módulos

| Área | Status | Interface |
|---|---|---|
| SSH/Telnet | uso básico | API Python e CLI |
| Ping/scan/traceroute | uso básico | API Python e CLI |
| MTR | uso básico com tabela ao vivo | API Python e CLI |
| SNMP v2c GET/WALK | uso básico | API Python e CLI |
| SFTP | operações de arquivo básicas | API Python e CLI |
| HTTP/FTP | cliente simples | API Python |

CLI básica:

```bash
maxconn --version
maxconn selftest
maxconn hosts add olt-01 --host 10.0.0.1 --port 22 --protocol ssh --username admin --profile huawei --tags olt,pop-centro
maxconn hosts list
maxconn hosts recent
maxconn hosts save-recent 1 --name olt-01 --profile huawei --tags olt
maxconn hosts test olt-01
maxconn history list
maxconn history show 1
maxconn history clear
maxconn ssh olt-01
maxconn ssh olt-01 --command "display version"
maxconn start
maxconn ping 192.0.2.1
maxconn ping 192.0.2.1 --output json --export ping.json
maxconn scan 192.0.2.1 --ports 22,23,80,443
maxconn scan 192.0.2.1 --ports 22,80,443 --json
maxconn discover 192.168.0.0/24
maxconn discover 192.168.0.0/24 --ports 80,443 --json
maxconn discover 192.168.0.0/24 --only-open
maxconn discover 192.168.0.0/24 --save-found
maxconn traceroute 8.8.8.8
maxconn traceroute 8.8.8.8 --output json
maxconn mtr 8.8.8.8
maxconn mtr 8.8.8.8 --count 5 --interval 1
maxconn mtr 8.8.8.8 --rediscover-every 30
maxconn mtr 8.8.8.8 --count 5 --json
maxconn mtr 8.8.8.8 --count 5 --output json
maxconn mtr 8.8.8.8 --count 5 --export mtr-report.txt --no-clear
maxconn sftp ls 192.0.2.10 /configs --username admin --password secret
maxconn sftp get 192.0.2.10 /remote/startup.cfg ./startup.cfg --username admin --password secret
maxconn sftp put 192.0.2.10 ./backup.cfg /remote/backup.cfg --username admin --password secret
maxconn sftp stat 192.0.2.10 /remote/startup.cfg --username admin --password secret
maxconn sftp stat 192.0.2.10 /remote/startup.cfg --username admin --password secret --json
maxconn sftp mkdir 192.0.2.10 /remote/new-folder --username admin --password secret
maxconn sftp rm 192.0.2.10 /remote/old.cfg --username admin --password secret
maxconn sftp rename 192.0.2.10 /remote/a.cfg /remote/b.cfg --username admin --password secret
maxconn doctor
maxconn snmp get 192.0.2.1 1.3.6.1.2.1.1.5.0 --community public
maxconn snmp get 192.0.2.1 1.3.6.1.2.1.1.5.0 --community public --json --retries 2
maxconn snmp walk 192.0.2.1 1.3.6.1.2.1.1 --community public
maxconn snmp walk 192.0.2.1 1.3.6.1.2.1.1 --community public --output json
maxconn ssh 192.0.2.10 --username admin --password secret --command "show version"
maxconn telnet 192.0.2.20 --username admin --password secret --command "show status"
```

Hosts salvos ficam em `~/.maxconn/hosts.json`. Hosts usados recentemente ficam
em `~/.maxconn/seen_hosts.json`, sem senha. Para salvar senha localmente, use
`--save-password` de forma explícita; ela não aparece em `hosts list`.
Histórico local fica em `~/.maxconn/history.jsonl`; comandos com palavras como
senha, token ou secret são gravados com redação.

Para entrar no terminal do equipamento, use `maxconn ssh NOME` ou
`maxconn telnet NOME` sem `--command`. Dentro do terminal visual aberto por
`maxconn start`, use `ssh NOME`, `telnet NOME` ou `open NOME`.

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

Discover de bloco:

```python
import maxconn

for host in maxconn.discover("192.168.0.0/24"):
    if host.reachable:
        print(host.host, host.open_ports)
```

No terminal, `maxconn discover REDE/CIDR` testa portas TCP comuns em todos os
hosts do bloco. As portas padrão incluem pelo menos `80` e `443`, junto com
portas comuns de rede como SSH, Telnet, SNMP, MikroTik e HTTP/HTTPS alternativo.
Use `--ports` para limitar ou alterar a lista.

Traceroute e mini MTR:

```python
import maxconn

trace = maxconn.traceroute("8.8.8.8")
for hop in trace.hops:
    print(hop.hop, hop.address)

report = maxconn.mtr("8.8.8.8", count=5)
print(report.loss_percent, report.avg)
```

No terminal, `maxconn mtr HOST` roda continuamente e atualiza uma tabela por
hop. Use `Ctrl+C` para parar. Para uma execução limitada, informe `--count`.
Saltos que não respondem aparecem como `No response from host`, para preservar
o caminho sem misturar o marcador interno `*` na tabela.
Por padrão a rota é descoberta uma vez e os hops conhecidos são medidos a cada
rodada, o que deixa a atualização mais parecida com WinMTR. Em redes com muitos
saltos silenciosos, aumente `--trace-timeout`. Para redescobrir a rota de tempos
em tempos, use `--rediscover-every N`.
Para automação e relatórios, use `--json`, `--output json`, `--export caminho.txt` e `--no-clear`.

### Exemplos

A pasta `examples/` tem scripts pequenos para servir como ponto de partida:

- `ssh_run_command.py`
- `sftp_backup.py`
- `mtr_report.py`
- `snmp_walk.py`
- `scan_ports.py`

Antes de publicar uma versão, rode:

```bash
python scripts/release_check.py
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

SFTP inicial:

```python
import maxconn

sftp = maxconn.connect_sftp(
    "192.0.2.40",
    username="user",
    password="secret",
)
try:
    print(sftp.listdir("/configs"))
    print(sftp.stat("/configs/startup.cfg"))
    sftp.download("/configs/startup.cfg", "startup.cfg")
    sftp.upload("backup.cfg", "/configs/backup.cfg")
    sftp.mkdir("/configs/archive")
    sftp.rename("/configs/backup.cfg", "/configs/archive/backup.cfg")
    sftp.remove("/configs/archive/old.cfg")
finally:
    sftp.close()
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

Current development version: `0.1.19`.

### Module Status

| Area | Status | Interface |
|---|---|---|
| SSH/Telnet | basic usage | Python API and CLI |
| Ping/scan/traceroute | basic usage | Python API and CLI |
| MTR | basic live table | Python API and CLI |
| SNMP v2c GET/WALK | basic usage | Python API and CLI |
| SFTP | basic file operations | Python API and CLI |
| HTTP/FTP | small client | Python API |

Basic CLI:

```bash
maxconn --version
maxconn selftest
maxconn hosts add olt-01 --host 10.0.0.1 --port 22 --protocol ssh --username admin --profile huawei --tags olt,pop-centro
maxconn hosts list
maxconn hosts recent
maxconn hosts save-recent 1 --name olt-01 --profile huawei --tags olt
maxconn hosts test olt-01
maxconn history list
maxconn history show 1
maxconn history clear
maxconn ssh olt-01
maxconn ssh olt-01 --command "display version"
maxconn start
maxconn ping 192.0.2.1
maxconn ping 192.0.2.1 --output json --export ping.json
maxconn scan 192.0.2.1 --ports 22,23,80,443
maxconn scan 192.0.2.1 --ports 22,80,443 --json
maxconn discover 192.168.0.0/24
maxconn discover 192.168.0.0/24 --ports 80,443 --json
maxconn discover 192.168.0.0/24 --only-open
maxconn discover 192.168.0.0/24 --save-found
maxconn traceroute 8.8.8.8
maxconn traceroute 8.8.8.8 --output json
maxconn mtr 8.8.8.8
maxconn mtr 8.8.8.8 --count 5 --interval 1
maxconn mtr 8.8.8.8 --rediscover-every 30
maxconn mtr 8.8.8.8 --count 5 --json
maxconn mtr 8.8.8.8 --count 5 --output json
maxconn mtr 8.8.8.8 --count 5 --export mtr-report.txt --no-clear
maxconn sftp ls 192.0.2.10 /configs --username admin --password secret
maxconn sftp get 192.0.2.10 /remote/startup.cfg ./startup.cfg --username admin --password secret
maxconn sftp put 192.0.2.10 ./backup.cfg /remote/backup.cfg --username admin --password secret
maxconn sftp stat 192.0.2.10 /remote/startup.cfg --username admin --password secret
maxconn sftp stat 192.0.2.10 /remote/startup.cfg --username admin --password secret --json
maxconn sftp mkdir 192.0.2.10 /remote/new-folder --username admin --password secret
maxconn sftp rm 192.0.2.10 /remote/old.cfg --username admin --password secret
maxconn sftp rename 192.0.2.10 /remote/a.cfg /remote/b.cfg --username admin --password secret
maxconn doctor
maxconn snmp get 192.0.2.1 1.3.6.1.2.1.1.5.0 --community public
maxconn snmp get 192.0.2.1 1.3.6.1.2.1.1.5.0 --community public --json --retries 2
maxconn snmp walk 192.0.2.1 1.3.6.1.2.1.1 --community public
maxconn snmp walk 192.0.2.1 1.3.6.1.2.1.1 --community public --output json
maxconn ssh 192.0.2.10 --username admin --password secret --command "show version"
maxconn telnet 192.0.2.20 --username admin --password secret --command "show status"
```

Saved hosts live in `~/.maxconn/hosts.json`. Recently used hosts live in
`~/.maxconn/seen_hosts.json`, without passwords. To save a password locally,
use `--save-password` explicitly; it is not shown in `hosts list`.
Local command history lives in `~/.maxconn/history.jsonl`; commands containing
words such as password, token, or secret are stored with redaction.

To enter a device terminal, run `maxconn ssh NAME` or `maxconn telnet NAME`
without `--command`. Inside the visual shell opened by `maxconn start`, use
`ssh NAME`, `telnet NAME`, or `open NAME`.

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

Subnet discovery:

```python
import maxconn

for host in maxconn.discover("192.168.0.0/24"):
    if host.reachable:
        print(host.host, host.open_ports)
```

In the terminal, `maxconn discover NETWORK/CIDR` tests common TCP ports across
the subnet. The default ports include at least `80` and `443`, plus common
network ports such as SSH, Telnet, SNMP, MikroTik, and alternate HTTP/HTTPS.
Use `--ports` to limit or change the list.

Traceroute and mini MTR:

```python
import maxconn

trace = maxconn.traceroute("8.8.8.8")
for hop in trace.hops:
    print(hop.hop, hop.address)

report = maxconn.mtr("8.8.8.8", count=5)
print(report.loss_percent, report.avg)
```

In the terminal, `maxconn mtr HOST` runs continuously and refreshes a table per
hop. Stop it with `Ctrl+C`. For a bounded run, pass `--count`. Hops that do not
answer are shown as `No response from host`, so the path is not hidden and the
internal `*` marker does not leak into the table.
By default the route is discovered once and known hops are measured every round,
which makes refreshes closer to WinMTR. On networks with many silent hops,
increase `--trace-timeout`. To refresh the route periodically, use
`--rediscover-every N`.
For automation and reports, use `--json`, `--output json`, `--export path.txt`, and `--no-clear`.

### Examples

The `examples/` folder has small scripts that can be used as starting points:

- `ssh_run_command.py`
- `sftp_backup.py`
- `mtr_report.py`
- `snmp_walk.py`
- `scan_ports.py`

Before publishing a version, run:

```bash
python scripts/release_check.py
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

Initial SFTP:

```python
import maxconn

sftp = maxconn.connect_sftp(
    "192.0.2.40",
    username="user",
    password="secret",
)
try:
    print(sftp.listdir("/configs"))
    print(sftp.stat("/configs/startup.cfg"))
    sftp.download("/configs/startup.cfg", "startup.cfg")
    sftp.upload("backup.cfg", "/configs/backup.cfg")
    sftp.mkdir("/configs/archive")
    sftp.rename("/configs/backup.cfg", "/configs/archive/backup.cfg")
    sftp.remove("/configs/archive/old.cfg")
finally:
    sftp.close()
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
