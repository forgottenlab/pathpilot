# Security Policy

## Supported versions

PathPilot is an alpha-stage project. Security fixes are provided only for the
latest code on the `main` branch and the latest published version. Older
prototype versions may not receive security updates.

## Reporting a vulnerability

Use the repository's **GitHub Security Advisory** reporting flow as the
preferred private channel:

https://github.com/forgottenlab/pathpilot/security/advisories/new

Do not put sensitive security details in a public issue. In particular, never
post exploit payloads, tokens, private keys, real user paths, private
configuration, or malicious installer files. A minimal description using
redacted paths and inert fixtures is sufficient for initial triage.

## Current security boundary

- Every installer suggestion defaults to `suggest` and needs explicit user
  confirmation before launch.
- File names and installer-family heuristics provide recommendations; they do
  not establish trust.
- Command previews are display-only and are never executed as shell strings.
- Legacy command-only queue records are marked `legacy_unsafe` and cannot run.
- Installer paths must remain inside the managed `_IncomingInstallers` tree.
- Installation targets must remain below the managed `Apps` root.
- `--force` confirms a launch but cannot bypass safety checks.
- `launched` means only that a process started. It does not mean installed,
  completed, verified, or successful.

PathPilot does **not** currently provide Authenticode signature or publisher
trust decisions, and it does not track installation completion.
