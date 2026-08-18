# MAXCONN

[![PyPI](https://img.shields.io/pypi/v/maxconn.svg)](https://pypi.org/project/maxconn/)
[![Python](https://img.shields.io/pypi/pyversions/maxconn.svg)](https://pypi.org/project/maxconn/)
[![CI](https://github.com/mmaxjr/maxconn/actions/workflows/ci.yml/badge.svg)](https://github.com/mmaxjr/maxconn/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Read in [English](README.md).

Biblioteca de automação de redes em Python, sem dependências obrigatórias:
clientes SSH/Telnet feitos sobre sockets puros (sem Paramiko/Netmiko/Scrapli),
uma CLI para tarefas do dia a dia de um engenheiro de redes, e um terminal
interativo com temas.

## Começo Rápido

```bash
pip install maxconn
maxconn hosts add olt-01 --host 10.0.0.1 --port 22 --protocol ssh --username admin
maxconn ssh olt-01 --command "show version"
```

Prefere Python puro? A mesma ideia, em três linhas:

```python
import maxconn

with maxconn.connect("192.0.2.10", protocol="ssh", username="admin", password="secret") as conn:
    print(conn.run("display version", prompt_markers=(">", "#")).text)
```

## Por que MAXCONN

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

## Instalação

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

Instalação para desenvolvimento:

```bash
git clone https://github.com/mmaxjr/maxconn
cd maxconn
pip install -e ".[dev]"
pytest -v
ruff check src tests
```

Versão atual em desenvolvimento: `0.3.1`.

## Status dos módulos

| Área | Status | Interface |
|---|---|---|
| SSH/Telnet | uso básico | API Python e CLI |
| Ping/scan/traceroute | uso básico | API Python e CLI |
| MTR | uso básico com tabela ao vivo | API Python e CLI |
| SNMP v2c GET/WALK | uso básico | API Python e CLI |
| SFTP | operações de arquivo básicas | API Python e CLI |
| HTTP/FTP | cliente simples | API Python |

## Referência da CLI

### Conexão e hosts salvos

```bash
maxconn ssh 192.0.2.10 --username admin --password secret --command "show version"
maxconn telnet 192.0.2.20 --username admin --password secret --command "show status"
maxconn ssh olt-01                                  # sessão interativa (sem --command)
maxconn hosts add olt-01 --host 10.0.0.1 --port 22 --protocol ssh --username admin --profile huawei --tags olt,pop-centro
maxconn hosts list
maxconn hosts list --json
maxconn hosts show olt-01
maxconn hosts edit olt-01 --host 10.0.0.2           # alias: hosts set
maxconn hosts remove olt-01
maxconn hosts test olt-01
maxconn hosts test --all
maxconn hosts test --tag core
maxconn hosts export --file hosts-backup.json
maxconn hosts import --file hosts-backup.json
maxconn hosts run --all --command "show version"
maxconn hosts run --tag core --command "show version" --json
maxconn hosts recent
maxconn hosts save-recent 1 --name olt-01 --profile huawei --tags olt
maxconn start                                       # terminal interativo com temas
```

Autocomplete de shell (bash/zsh/PowerShell) para comandos e flags:

```bash
source <(maxconn completion bash)     # adicionar ao ~/.bashrc
source <(maxconn completion zsh)      # adicionar ao ~/.zshrc
maxconn completion powershell | Out-String | Invoke-Expression   # adicionar ao $PROFILE
```

Defaults locais, para não repetir `--timeout`/`--concurrency`/`--workers`/`--ports` em todo comando:

```bash
maxconn config set timeout 5
maxconn config set ports 22,80,443
maxconn config get timeout
maxconn config list
maxconn config unset timeout
```

### Backup e diff de configuração

```bash
maxconn backup olt-01                                        # usa o comando padrão do perfil salvo do host
maxconn backup 192.0.2.10 --username admin --password secret --command "show running-config" --to backup.cfg
maxconn diff backup-2026-08-01.cfg backup-2026-08-16.cfg      # código de saída 1 se forem diferentes
maxconn diff backup-2026-08-01.cfg backup-2026-08-16.cfg --json
```

Backups vão por padrão para `~/.maxconn/backups/<host>/<timestamp>.cfg`, a menos que `--to CAMINHO` seja informado. O comando padrão de backup é resolvido a partir do `--profile` salvo do host (`cisco`, `huawei`, `mikrotik`); use `--command` explicitamente para qualquer outro caso.

### Inventário

```bash
maxconn inventory
maxconn inventory --json
maxconn inventory --output csv --export inventario.csv
maxconn inventory --reconcile 192.168.0.0/24          # planejado (hosts salvos) vs. provisionado (scan ao vivo)
maxconn inventory --reconcile 192.168.0.0/24 --json
```

`--reconcile` roda um scan `discover` ao vivo na rede informada e reporta hosts salvos que não foram vistos alcançáveis ("documentado mas inalcançável") junto com hosts alcançáveis que não estão no inventário salvo ("não documentado"). O código de saída é `1` quando há divergência, `0` quando tudo bate - útil para checagens automatizadas.

### Descoberta

```bash
maxconn discover 192.168.0.0/24
maxconn discover 192.168.0.0/24 --ports 80,443 --json
maxconn discover 192.168.0.0/24 --only-open
maxconn discover 192.168.0.0/24 --save-found --name-prefix sw --tags discovered,lab
maxconn discover 10.0.0.0/20 --confirm             # exigido acima do limite de hosts
```

### Diagnóstico

```bash
maxconn ping 192.0.2.1
maxconn ping 192.0.2.1 --output json --export ping.json
maxconn scan 192.0.2.1 --ports 22,23,80,443
maxconn traceroute 8.8.8.8
maxconn mtr 8.8.8.8 --count 5 --interval 1
maxconn snmp get 192.0.2.1 1.3.6.1.2.1.1.5.0 --community public
maxconn snmp walk 192.0.2.1 1.3.6.1.2.1.1 --community public
maxconn doctor
maxconn doctor --network                            # + checagens de DNS/gateway/internet/versão PyPI
maxconn history list --limit 20 --since today
maxconn history show 1
maxconn history replay 1
maxconn history clear
maxconn selftest
maxconn config set audit_log on                      # grava o trilha de auditoria em ~/.maxconn/audit.jsonl
maxconn audit tail
maxconn audit tail -n 50 --json
maxconn config set update_notify on                  # aviso passivo de "nova versão disponível" após comandos
```

`update_notify` checa o PyPI no máximo uma vez a cada 24h (cache em `~/.maxconn/update_check.json`) e só imprime um aviso de uma linha no stderr quando existe uma versão mais nova - nunca bloqueia nem quebra um comando, mesmo se a checagem falhar.

### Transferência de arquivos (SFTP)

```bash
maxconn sftp ls 192.0.2.10 /configs --username admin --password secret
maxconn sftp get 192.0.2.10 /remote/startup.cfg ./startup.cfg --username admin --password secret
maxconn sftp put 192.0.2.10 ./backup.cfg /remote/backup.cfg --username admin --password secret
maxconn sftp stat 192.0.2.10 /remote/startup.cfg --username admin --password secret
maxconn sftp mkdir 192.0.2.10 /remote/new-folder --username admin --password secret
maxconn sftp rm 192.0.2.10 /remote/old.cfg --username admin --password secret
maxconn sftp rename 192.0.2.10 /remote/a.cfg /remote/b.cfg --username admin --password secret
```

Hosts salvos ficam em `~/.maxconn/hosts.json`. Hosts usados recentemente ficam
em `~/.maxconn/seen_hosts.json`, sem senha. Para salvar senha localmente, use
`--save-password` de forma explícita; ela nunca é exibida, e `hosts list`
mostra apenas um indicador sim/não de que existe senha salva.
Histórico local fica em `~/.maxconn/history.jsonl`; comandos com palavras como
senha, token ou secret são gravados com redação.

Para entrar no terminal do equipamento, use `maxconn ssh NOME` ou
`maxconn telnet NOME` sem `--command`. Dentro do terminal visual aberto por
`maxconn start`, use `ssh NOME`, `telnet NOME` ou `open NOME`.

## API Python

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
        print(host.host, host.open_ports, host.banner)
```

No terminal, `maxconn discover REDE/CIDR` testa portas TCP comuns em todos os
hosts do bloco. As portas padrão incluem pelo menos `80` e `443`, junto com
portas comuns de rede como SSH, Telnet, SNMP, MikroTik e HTTP/HTTPS alternativo.
Use `--ports` para limitar ou alterar a lista. Redes acima do limite de hosts
exigem `--confirm` (ou `confirm=True` em Python).

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

## Direção do Projeto

- Não transformar o projeto em wrapper de Paramiko, Netmiko, Scrapli ou Telnetlib.
- Manter dependências opcionais atrás de extras.
- Deixar bytes crus disponíveis para quem precisa.
- Dar uma API simples para o caso comum.
- Testar com servidores locais de Telnet e SSH sempre que fizer sentido.
- Publicar novas versões no PyPI por tag, usando GitHub Actions e Trusted Publishing.
