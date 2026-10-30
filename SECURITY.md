# Security policy

DeskBuddy stores passwords and notes in an encrypted vault, so security reports are taken seriously.

## Reporting a vulnerability

**Please don't open a public issue.** Use GitHub's private reporting instead: go to the repository's **Security** tab and click **Report a vulnerability**. Include steps to reproduce and the version (or commit) you tested.

You should get a reply within a week.

## Scope

In scope: the vault encryption and key handling, backups, the clipboard auto-clear, the local IPC socket, and the chat client/server.

Known limitations (documented in the README, not vulnerabilities):
- The master password can't be recovered.
- Clipboard-history tools may record copied secrets.
- The LAN chat server has no authentication; it identifies machines by IP address and is meant for trusted networks only.
