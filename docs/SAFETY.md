# Safety

NETA Lab scenarios are designed for controlled validation of NETA. Run them only on systems and networks you own or are explicitly authorized to test.

## Principles

- Prefer behavior emulation over exploit code.
- Do not target public or third-party infrastructure.
- Do not steal credentials, escalate privileges, evade controls, or deploy destructive payloads.
- Scenarios that change endpoint state must document cleanup and should make cleanup idempotent.
- Ground-truth markers are for validation only; NETA detection logic must not use them as a shortcut to classify behavior.
- HTTPS scenarios use lab certificates only. Certificate-validation bypasses in client scripts are intentional for isolated lab use and must not be copied into production software.

The initial HTTP and HTTPS beacon scenarios only create repeated outbound requests to a server controlled by the operator.
