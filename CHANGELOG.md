# Changelog

## 0.3.1 - 2026-08-18

- Fix `hosts run` aborting an entire batch (losing every other host's
  result) when one host raised an exception type other than
  `MaxConnError`/`OSError`/`TimeoutError`.
- Fix a corrupted or non-dict `~/.maxconn/config.json` crashing every
  single `maxconn` command instead of being treated as empty.
- Fix `enable_persistent_audit_log()` failures (e.g. an unwritable
  `~/.maxconn`) crashing the whole command instead of degrading
  gracefully, matching the update-notify code path.
- Fix `audit tail --json` aborting entirely on a single malformed line
  in `audit.jsonl` instead of skipping it.
- Fix `history list --limit 0` showing every entry instead of none
  (Python's `list[-0:]` is the whole list, not empty).

## 0.3.0 - 2026-08-17

- Add `maxconn hosts run --all`/`--tag TAG --command "..."` to run a
  command across multiple saved hosts concurrently.
- Add `maxconn backup HOST` to save a device's running configuration
  locally, with a per-profile default fetch command.
- Add `maxconn diff FILE1 FILE2` for a unified diff between two config
  backups.
- Add `maxconn inventory` to list saved hosts as a structured
  inventory (text/json/csv).
- Add `maxconn inventory --reconcile NETWORK` to compare saved hosts
  against a live `discover` scan (documented-but-unreachable /
  undocumented-but-reachable reporting).
- Add `maxconn audit tail` and an opt-in persistent audit log
  (`maxconn config set audit_log on`).
- Add an opt-in cached PyPI update-check notice
  (`maxconn config set update_notify on`), at most once per 24h.

## 0.2.0 - 2026-08-16

- Fix SSH session-key derivation for the `diffie-hellman-group14-sha1`/`hmac-sha1`
  compatibility fallback, which previously could never complete a handshake.
- Fix a discarded server-to-client MAC negotiation result and add DH public-value
  range validation (forward-secrecy hardening).
- Enforce the negotiated SSH host-key algorithm and raise `ProtocolError` instead
  of a raw exception on malformed EC points; add an SSH packet-length upper bound.
- Fix SNMP UDP responses being accepted from any source address (spoofing risk);
  responses are now validated against the resolved target host.
- Fix resource leaks: `SessionManager.close_all()`/`add()`, `maxconn.connect()`,
  and `FTPClient.connect()` could leak sockets on error or overwrite.
- Consolidate duplicated secret-redaction logic into `maxconn._redact`.
- Add file locking against concurrent `hosts.json`/`history.jsonl` writes.
- Unify the theme config directory under `~/.maxconn`.
- `Connection.recv()` / `Transport.recv()` now default to a 30s timeout instead
  of blocking forever.
- `net.scan()` now bounds DNS resolution by the caller's `timeout`.
- Telnet IAC subnegotiation now has a buffer size cap, raising `ProtocolError`
  instead of growing unbounded.
- Add `history list --limit`, `--since`, `--json`, `--output csv`, `--export`.
- Add `history replay ID` to re-run a saved or recent command.
- Add `discover` banner fingerprinting on the first open port per host.
- Add `discover --confirm` guard for networks above a host-count threshold.
- Add `discover --save-found --name-prefix`/`--tags`.
- Add `hosts edit`/`hosts set` to update fields on a saved host.
- Add `hosts test --all` and `hosts test --tag`.
- Add `hosts export`/`hosts import` for backing up saved hosts.
- Add `hosts list --json` and a saved-password indicator (never the value).
- Add `doctor --network` with DNS, internet, gateway, and PyPI version checks.
- Add `doctor` checks for `~/.maxconn` writability and terminal/color capability.
- Split the README into `README.md` (English) and `README.pt-BR.md`, add a
  Quick Start section, and group the CLI reference by category.
- Add the missing `py.typed` marker file so type checkers actually use
  maxconn's type hints when it's installed as a dependency (the package
  already declared `Typing :: Typed` but never shipped the marker).
- Make `HistoryStore._next_id()` O(1) instead of parsing the whole
  `history.jsonl` file on every command execution.
- Run `hosts test --all`/`--tag` scans concurrently instead of one host
  at a time.
- Add `maxconn completion {bash,zsh,powershell}` for native shell
  completion of commands and flags.
- Add `maxconn config set/get/unset/list` for local CLI defaults
  (`timeout`, `concurrency`, `workers`, `ports`).
- Split `cli.py` into a `maxconn/cli/` package, one module per command
  group, for maintainability (no behavior change).

## 0.1.19 - 2026-08-14

- Add local command history with `maxconn history list/show/clear`.
- Add `maxconn hosts test HOST` to verify a saved host port.
- Add `maxconn discover --only-open` and `--save-found`.

## 0.1.18 - 2026-08-13

- Add `maxconn discover NETWORK/CIDR` for subnet TCP discovery.
- Use common network ports by default, including HTTP `80` and HTTPS `443`.
- Add `--ports`, `--timeout`, `--workers`, `--json`, and `--export` for discovery scans.

## 0.1.17 - 2026-08-13

- Remove preview-only future commands from `maxconn start` help/completion.
- Dispatch real CLI commands such as `hosts`, `sftp`, `snmp`, `doctor`, and `selftest` from inside `maxconn start`.

## 0.1.16 - 2026-08-13

- Avoid repeated line redraws when pasting long commands into `maxconn start`.
- Allow `maxconn hosts add --password ... --save-password` to save a password explicitly.
- Allow `maxconn hosts add --ask-password --save-password` for prompted password saving.

## 0.1.15 - 2026-08-13

- Keep the saved `maxconn start` theme around interactive SSH/Telnet device sessions.
- Render interactive connection status and device prompts with the current theme.
- Preserve raw device output while styling only MaxConn-owned terminal text.

## 0.1.14 - 2026-08-13

- Add SSH `ecdh-sha2-nistp256` key exchange compatibility.
- Add SSH `ecdsa-sha2-nistp256` host-key signature verification.
- Add legacy `diffie-hellman-group14-sha1` and `hmac-sha1` negotiation fallback.
- Accept OpenSSH-style `username@host` syntax for SSH/Telnet CLI commands.

## 0.1.13 - 2026-08-13

- Add left/right cursor movement inside `maxconn start`.
- Allow editing recalled history commands before pressing Enter.
- Keep insertion, backspace, Tab completion, and `?` help working with the line cursor.

## 0.1.12 - 2026-08-13

- Keep `maxconn start` running when SSH/Telnet connection setup fails.
- Print clean connection errors instead of Python tracebacks for MaxConn protocol failures.
- Show a short usage hint for `ssh` or `telnet` with no host inside the interactive shell.

## 0.1.11 - 2026-08-13

- Allow `maxconn ssh HOST` and `maxconn telnet HOST` to open an interactive line-by-line device terminal.
- Keep `--command` available for one-shot command execution.
- Wire `ssh`, `telnet`, and `open HOST` inside `maxconn start` to the real CLI flow.
- Keep saved-host aliases and saved credentials working in interactive sessions.

## 0.1.10 - 2026-08-13

- Add local saved hosts with `maxconn hosts add/list/show/remove`.
- Add recent host tracking with `maxconn hosts recent` and `save-recent`.
- Allow SSH/Telnet commands to resolve saved host aliases.
- Add `--save` for SSH/Telnet connections.
- Allow explicit local password saving with `--save-password`, keeping passwords out of tables and recent-host records.

## 0.1.9 - 2026-08-12

- Add JSON/export output to `ping`, `scan`, `traceroute`, `snmp get`, `snmp walk`, and `sftp stat`.
- Add `--output json` aliases while keeping existing `--json` flags.
- Add `maxconn selftest` for quick local CLI checks.
- Add retry support for SNMP CLI calls and ping attempt aliases.
- Improve CLI help text and user-facing error messages.
- Add release check tooling and practical example scripts.

## 0.1.8 - 2026-08-12

- Add `maxconn sftp stat`, `mkdir`, `rm`, and `rename`.
- Add SFTP `stat`, `mkdir`, `remove`, and `rename` APIs.
- Add `maxconn mtr --json`, `--export`, and `--no-clear`.
- Add `maxconn doctor` for local environment diagnostics.
- Improve MTR JSON rendering for automation/reporting.

## 0.1.7 - 2026-08-11

- Add initial SFTP client over maxconn's SSH channel subsystem.
- Add `maxconn sftp ls`, `maxconn sftp get`, and `maxconn sftp put`.
- Make `maxconn mtr` discover the route once and update known hops every round.
- Add `--rediscover-every` for periodic MTR route refresh.

## 0.1.6 - 2026-08-10

- Polish `maxconn mtr` output for silent hops.
- Show `No response from host` instead of the internal `*` marker.
- Render loss and latency values with clearer `%` and `ms` units.

## 0.1.5 - 2026-08-10

- Keep timed-out traceroute hops in `maxconn mtr` output instead of hiding them.
- Avoid pinging `*` placeholder hops.
- Improve WinMTR-style path display when intermediate routers do not answer.

## 0.1.4 - 2026-08-10

- Change `maxconn mtr HOST` to run continuously by default.
- Add WinMTR-style hop table for `maxconn mtr`.
- Keep bounded runs available through `maxconn mtr HOST --count N`.
- Add `--interval` for MTR refresh timing.

## 0.1.3 - 2026-08-10

- Add `maxconn traceroute` using the platform traceroute command.
- Add `maxconn mtr` as a small repeated-ping report.
- Add dependency-free SNMP v2c `get`, `getnext`, and `walk`.
- Add `maxconn snmp get` and `maxconn snmp walk` CLI commands.
- Add README examples for traceroute, MTR, and SNMP.

## 0.1.2 - 2026-08-10

- Add `maxconn --version`.
- Add `maxconn ping` and `maxconn scan` CLI commands.
- Add from-scratch TCP port scanner in `maxconn.net.scan`.
- Add basic dependency-free HTTP/HTTPS client in `maxconn.protocol.http`.
- Add basic passive-mode FTP client in `maxconn.protocol.ftp`.
- Refresh README examples for CLI, scan, HTTP, and FTP.

## 0.1.1 - 2026-08-10

- Add `SessionManager` for named connection lifecycle control.
- Add `maxconn` CLI for basic SSH and Telnet command execution.
- Add confirmation handling and `wait_for()` to `ExpectSession`.
- Add JSON audit logging helper.
- Add `maxconn.net.ping`.
- Add MIT license.

## 0.1.0 - 2026-08-10

- First PyPI release.
- Add raw-socket Telnet and SSH transports.
- Add prompt/expect command automation.
- Add `Connection.run()` and structured command results.
