# NETA-LAB-004 — TerminalFix/ClickFix-Style Safe Chain

## Purpose

Validate the same endpoint-causality pattern on Windows and Linux: a launcher starts a script-capable process, a benign NETA-owned artifact is downloaded, that artifact executes, and the new process performs one HTTPS callback to controlled infrastructure.

The scenario is intentionally benign. It does not exploit software, create persistence, access credentials, modify security settings, or execute commands received from the server.

## Platform semantics

Windows keeps the original chain:

```text
cmd.exe -> powershell.exe -> download benign .exe -> execute -> HTTPS callback
```

Linux preserves the same causal meaning with native shell tooling:

```text
bash -> curl -> downloaded executable shell payload -> HTTPS callback
```

The Linux payload is repository-authored source, served by the same controlled scenario server, written into a temporary user-writable directory, hashed, marked executable, run once, and removed automatically.

## Controlled server

The HTTPS server is `server/lab_https_server.py`. It serves exactly one selected benign payload route plus `/callback` and emits JSON-line ground truth. Its payload path and route are configurable so Windows and Linux can share one scenario ID without pretending their artifacts are identical.

Windows retains the default route `/payload/neta-lab-004-payload.exe`. Linux full-cycle acceptance uses `/payload/neta-lab-004-payload.sh` on a separate controlled port.

## Linux run

```bash
./linux/run.sh <LAB-HOST> [port=18444] [ca-cert]
```

For full-cycle acceptance the CA is supplied through `NETA_LAB_CA_CERT`. Certificate verification remains enabled. `NETA_LAB_TLS_INSECURE=1` exists only for explicitly isolated ad-hoc testing and is not used by full-cycle acceptance.

Linux ground truth includes the run ID, download URL, temporary artifact path, and SHA-256. Required NETA semantics remain process lifecycle, parent/child causality, file creation/hash, process attribution, outbound connection evidence, and TLS identity where supported.

## Windows run

Use the existing Windows implementation under `windows/`; it keeps the original PowerShell and benign executable behavior documented by the scenario's platform expectations.

## Expected finding

```text
SCRIPTED_DOWNLOAD_EXECUTE_NETWORK_CHAIN
```

Interpretation must stay behavioral: a script-capable process downloaded an executable artifact, started it, and the new process communicated over the network. The sequence is compatible with TerminalFix/ClickFix-style delivery behavior, but malicious intent is not established by this lab.

Detection must not key on scenario IDs, run IDs, filenames, HTTP headers, callback paths, or server ground-truth markers.

## Safety and cleanup

Run only against systems you own or are explicitly authorized to test. Linux temporary artifacts are removed automatically. Stop the controlled HTTPS server after the test.
