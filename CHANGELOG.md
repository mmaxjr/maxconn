# Changelog

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
