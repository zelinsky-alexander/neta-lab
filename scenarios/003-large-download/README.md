# NETA-LAB-003 — Controlled Large Download

## Purpose

Generate one controlled large inbound transfer over an outbound HTTP connection so NETA can validate per-process, per-connection transfer-volume evidence.

This scenario is intentionally benign. It does not execute downloaded content, establish persistence, exploit software, or contact third-party infrastructure.

## Behavior

A client endpoint downloads a deterministic byte stream from a NETA Lab server you control.

Default ground truth:

- protocol: HTTP over TCP,
- payload size: 50 MiB (52,428,800 bytes),
- connection count: one expected application transfer,
- client process: `curl` / `curl.exe`,
- direction: outbound connection with predominantly inbound application data.

The server records the requested scenario/run markers for independent validation. NETA detection must not depend on those markers.

## Why this scenario exists

NETA-LAB-001/002 validate temporal repetition. NETA-LAB-003 validates a different EDR primitive: cumulative transfer volume associated with a process and connection.

TCP receive-queue size is not cumulative bytes received and must not be used as a substitute. If the current agent cannot provide reliable cumulative byte accounting, the correct result is a documented capability gap rather than an inferred byte count.

## Start the controlled server

From the repository root:

```bash
python3 scenarios/003-large-download/server/large_download_server.py --bind 0.0.0.0 --port 18080 --size-mib 50
```

Use a private/LAN address reachable from the observed client where possible.

## Linux client

```bash
./scenarios/003-large-download/linux/run.sh <LAB-SERVER-IP> [port=18080] [size_mib=50]
```

The downloaded payload is written to a temporary file, size-checked, then deleted.

## Windows client

```powershell
.\scenarios\003-large-download\windows\run.ps1 -HostAddress <LAB-SERVER-IP> [-Port 18080] [-SizeMiB 50]
```

The downloaded payload is written under the user's temporary directory, size-checked, then deleted.

## Independent ground truth

For the default run the server intends to serve exactly 52,428,800 payload bytes. The client verifies the resulting file size before cleanup.

Expected application-level ground truth:

```text
process: curl / curl.exe
remote endpoint: configured lab server:18080
payload bytes received: 52,428,800
connection behavior: one large download
```

HTTP headers and TCP framing add transport overhead. NETA's cumulative network-byte evidence may therefore differ slightly depending on the semantic counter being exposed. The evidence field must state exactly what it measures.

## Expected NETA evidence

Required for full PASS:

- outbound connection observed,
- correct remote endpoint,
- process attribution,
- reliable cumulative received-byte evidence for the connection,
- evidence provenance/fidelity,
- transfer size consistent with the 50 MiB ground truth within the defined tolerance.

Supporting evidence when available:

- TCP metrics,
- route/interface evidence,
- DNS evidence if a hostname is used.

## Expected finding

Once cumulative byte accounting is implemented, the initial semantic finding is:

```text
LARGE_INGRESS_TRANSFER
```

Recommended interpretation:

> A process received an unusually large volume of data from a remote endpoint during a connection. Malicious intent is not established.

The initial detector threshold should be independent of the scenario payload; for example, a 32 MiB threshold can detect the default 50 MiB run.

## Expected end-to-end flow

```text
curl / curl.exe
      |
      +-- outbound TCP connection
      |
      +-- controlled 50 MiB download
      |
      +-- cumulative received-byte evidence
      |
      v
LARGE_INGRESS_TRANSFER
      |
      v
coordinator
      |
      v
portal
```

## Acceptance criteria

For a fully capable agent:

```text
connection observed          PASS
process attribution          PASS
direction                    PASS
remote endpoint              PASS
received-byte evidence       PASS
transfer-size tolerance      PASS
finding generated            PASS
coordinator received         PASS
portal visible               PASS
```

If cumulative received-byte evidence is unavailable, report that item and the finding as unsupported/not yet implemented. Do not fabricate a PASS from queue-depth samples.

## Cleanup

The client scripts remove their temporary payload automatically. Stop the server with Ctrl+C. No persistent endpoint changes are made.
