# Changelog

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
