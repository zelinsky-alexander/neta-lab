# NETA-LAB-004 — TerminalFix/ClickFix-Style Safe Chain

## Purpose

Emulate the first MS11 endpoint attack-chain scenario from the NETA EDR roadmap without malware, exploitation, persistence, credential access, or third-party infrastructure.

The controlled chain is:

```text
test launcher (cmd.exe)
    -> PowerShell
    -> HTTPS download of a benign NETA-owned executable
    -> downloaded executable starts
    -> executable connects to the same controlled HTTPS server
```

This scenario is designed to validate endpoint causality, not merely network activity.

## Safety boundary

`NETA-LAB-004` is intentionally benign:

- the downloaded executable is built from source in this repository,
- it only performs one HTTPS GET to the configured lab server,
- it does not execute commands received from the server,
- it does not create persistence,
- it does not read credentials or secrets,
- it does not modify security settings,
- it does not exploit software,
- it does not contact any endpoint other than the explicitly configured lab host.

Run it only on systems and endpoints you own or are explicitly authorized to test.

## Expected process/file/network chain

For the default Windows run:

```text
cmd.exe
  `-- powershell.exe
        |-- writes downloaded file --> neta-lab-004-payload.exe
        `-- starts --> neta-lab-004-payload.exe
                        `-- HTTPS GET --> https://<lab-host>:18443/callback
```

The download itself is also HTTPS:

```text
powershell.exe
  `-- curl.exe --> https://<lab-host>:18443/payload/neta-lab-004-payload.exe
```

The `curl.exe` process is an implementation detail of the safe downloader. The core causal chain to validate is launcher -> PowerShell -> downloaded executable -> controlled HTTPS connection, while preserving the intermediate download process/file evidence.

## 1. Build the benign payload on Windows

From the repository root in Windows PowerShell:

```powershell
.\scenarios\004-terminalfix-style-chain\windows\build-payload.ps1
```

This produces:

```text
scenarios/004-terminalfix-style-chain/server/payload/neta-lab-004-payload.exe
```

The executable is generated from `payload/NetaLab004Payload.cs`. No prebuilt binary is committed.

## 2. Create a lab TLS certificate

Use a certificate whose SAN matches the hostname you will pass to `-LabHost`. For a local-only example using `neta-lab.local`, OpenSSL can be used to generate a short-lived self-signed lab certificate:

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 7 \
  -keyout neta-lab-004-key.pem \
  -out neta-lab-004-cert.pem \
  -subj '/CN=neta-lab.local' \
  -addext 'subjectAltName=DNS:neta-lab.local'
```

Ensure the observed Windows host resolves that hostname to the controlled lab server, for example through lab DNS or an authorized hosts-file entry.

## 3. Start the controlled HTTPS server

```bash
python3 scenarios/004-terminalfix-style-chain/server/lab_https_server.py \
  --bind 0.0.0.0 \
  --port 18443 \
  --cert neta-lab-004-cert.pem \
  --key neta-lab-004-key.pem
```

The server exposes only two scenario resources:

- `/payload/neta-lab-004-payload.exe` — the benign executable,
- `/callback` — the executable's final HTTPS request.

It logs independent ground-truth events as JSON lines.

## 4. Run the Windows chain

Copy the server certificate PEM to the Windows test host, then run through the test launcher:

```cmd
scenarios\004-terminalfix-style-chain\windows\launch.cmd -LabHost neta-lab.local -ServerCertificatePath C:\lab\neta-lab-004-cert.pem
```

Optional parameters can be passed through to `run.ps1`, including `-Port` and `-KeepDownloadedArtifact`.

`-KeepDownloadedArtifact` is useful when you want to inspect the dropped executable after the run. By default the temporary scenario directory is removed after execution.

## Independent ground truth

The PowerShell runner prints:

- scenario run ID,
- download URL,
- destination path,
- downloaded artifact SHA-256,
- child executable PID,
- child exit code.

The HTTPS server separately logs:

- payload download request,
- callback request,
- run ID,
- client address,
- request timestamp.

These markers exist only for validation. NETA detections must not depend on scenario headers, paths, run IDs, filenames, or the server's log markers.

## Expected NETA evidence

Required for a full L1 PASS when the corresponding EDR capabilities exist:

- process start for the launcher,
- process start for PowerShell,
- parent/child relation launcher -> PowerShell,
- file creation for the downloaded executable,
- downloaded executable path,
- downloaded executable SHA-256,
- process start for the downloaded executable,
- parent/child relation PowerShell -> downloaded executable,
- DNS evidence for the configured lab hostname,
- outbound connection attributed to the downloaded executable,
- TLS identity evidence for that connection,
- final correlated finding preserving the supporting evidence chain.

Supporting evidence when available:

- user/logon identity,
- executable signer state (the lab payload is expected to be unsigned unless you explicitly sign it),
- route/interface evidence,
- TCP metrics,
- first-seen executable state.

## Expected finding

The initial semantic finding is:

```text
SCRIPTED_DOWNLOAD_EXECUTE_NETWORK_CHAIN
```

Recommended interpretation:

> A script-capable process downloaded an executable, started it, and the new process initiated network communication to a destination. This behavior is compatible with a TerminalFix/ClickFix-style delivery chain. Malicious intent is not established by this sequence alone.

The detector must correlate real endpoint evidence. It must not key on `NETA-LAB-004`, the payload filename, HTTP headers, the callback path, or other lab-only markers.

## Acceptance criteria

```text
launcher process observed                 PASS
launcher -> PowerShell parent chain       PASS
PowerShell process observed               PASS
download connection observed              PASS
downloaded file creation observed         PASS
artifact SHA-256 available                PASS
PowerShell -> payload parent chain         PASS
payload process observed                  PASS
payload DNS evidence                      PASS
payload outbound connection               PASS
payload TLS identity                      PASS
correlated finding generated              PASS
coordinator received evidence/finding     PASS
portal investigation is explainable       PASS
```

If a required collector is not yet implemented, report the specific item as unsupported/not yet implemented. Do not infer file creation, artifact identity, parentage, DNS, or TLS from lab ground truth.

## Cleanup

By default `run.ps1` removes its temporary directory after the payload exits. With `-KeepDownloadedArtifact`, remove the printed temporary directory manually after investigation. Stop the lab HTTPS server with Ctrl+C.
