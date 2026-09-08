# NETA-LAB-005 — LOLBin Staging Chain

## Purpose

Implement MS11 L2 from the NETA EDR roadmap: use legitimate Windows system utilities in an intentionally unusual but harmless sequence and prove that NETA does not equate signed software with safe behavior.

The controlled chain is:

```text
cmd.exe test launcher
    -> powershell.exe
        -> certutil.exe downloads inert text from a controlled HTTP endpoint
        -> certutil.exe Base64-encodes the text
        -> certutil.exe decodes it to a second file
        -> powershell.exe validates hashes
        -> powershell.exe performs one controlled HTTP callback
```

No executable is downloaded or launched by this scenario.

## Why this is a LOLBin scenario

`certutil.exe` is a legitimate Windows utility. The lab intentionally uses supported file/network/encoding functionality in a sequence that is unusual enough to be security-relevant while remaining harmless.

The point is not that `certutil.exe` is malicious. The point is that trust in the executable signer must not erase behavioral evidence.

A useful investigation should be able to say, in effect:

> A signed system utility was launched from a scripting lineage, retrieved a new artifact, transformed it into additional files, and the initiating script then communicated with the same controlled endpoint.

## Safety boundary

`NETA-LAB-005` is intentionally benign:

- only deterministic plain-text lab content is downloaded,
- no executable, DLL, script, macro, archive, or shell command is downloaded,
- downloaded content is never executed,
- no persistence is created,
- no credentials, browser data, tokens, or secrets are accessed,
- no privilege transition is attempted,
- no security control is modified,
- no exploit is used,
- network traffic is limited to the explicitly configured lab server,
- temporary artifacts are removed by default.

Run it only on systems and endpoints you own or are explicitly authorized to test.

## Expected process/file/network chain

```text
cmd.exe
  `-- powershell.exe
        |-- certutil.exe -urlcache ... -> stage.txt
        |-- certutil.exe -encode ...   -> stage.b64
        |-- certutil.exe -decode ...   -> stage.decoded.txt
        `-- HTTP GET -> controlled /callback
```

`run.ps1` also records the local Authenticode status and signer subject of the system `certutil.exe` as independent ground truth. NETA must collect signer evidence independently; it must not consume the runner's result as telemetry.

## 1. Start the controlled server

From the repository root:

```bash
python3 scenarios/005-lolbin-chain/server/lab_http_server.py \
  --bind 0.0.0.0 \
  --port 18580
```

The server exposes only:

- `/stage.txt` — deterministic inert text,
- `/callback` — final success marker from the PowerShell runner.

Each request is logged as one JSON object for independent lab ground truth.

## 2. Run the Windows chain

From a Windows command prompt at the repository root:

```cmd
scenarios\005-lolbin-chain\windows\launch.cmd -HostAddress <LAB-SERVER-IP>
```

Optional parameters:

```text
-Port 18580
-KeepArtifacts
```

Example:

```cmd
scenarios\005-lolbin-chain\windows\launch.cmd -HostAddress 192.0.2.10 -Port 18580 -KeepArtifacts
```

Use the actual address of infrastructure you own; `192.0.2.10` above is documentation-only.

## Independent ground truth

The Windows runner prints:

- run ID,
- download URL,
- temporary artifact directory,
- SHA-256 of the downloaded text,
- SHA-256 after encode/decode round trip,
- `certutil.exe` Authenticode status,
- `certutil.exe` signer subject when available,
- final callback completion.

The server separately logs the stage request and callback request.

These markers are validation aids only. NETA detections must not depend on the scenario ID, run ID, lab paths, HTTP headers, server content, or temporary filenames.

## Expected NETA evidence

Required for the core behavioral PASS when corresponding EDR collectors exist:

- launcher process start,
- PowerShell process start,
- parent/child relation `cmd.exe -> powershell.exe`,
- all `certutil.exe` process starts,
- parent/child relation `powershell.exe -> certutil.exe`,
- command-line evidence sufficient to distinguish download / encode / decode operations,
- downloaded file creation,
- encoded file creation,
- decoded file creation,
- file paths and hashes when hashing capability exists,
- outbound connection associated with the staging activity,
- final correlated finding preserving underlying evidence.

Required for the roadmap's signed-software proof:

- image/signature evidence for `certutil.exe`,
- signer verdict represented independently from behavioral verdict,
- a signed/valid signer state must not suppress the suspicious behavioral correlation.

Supporting evidence when available:

- user/logon identity,
- DNS evidence if a hostname is used,
- route/interface evidence,
- TCP metrics,
- first-seen artifact state.

## Expected finding

The initial semantic finding is:

```text
SIGNED_SYSTEM_UTILITY_STAGING_CHAIN
```

Recommended interpretation:

> A legitimate signed system utility performed an unusual staged download and file transformation sequence from a scripting lineage, followed by related network activity. The signer is trusted as publisher identity evidence, but the observed behavior remains security-relevant. Malicious intent is not established by this sequence alone.

The finding should remain explainable from process, command-line, file, signer, and network evidence.

## Detection guardrails

A valid detector may use semantic facts such as:

- execution of a known system utility,
- signer state,
- download-related command-line behavior,
- repeated file transformation activity,
- scripting parentage,
- related network activity.

It must not key on lab-only facts such as:

- `NETA-LAB-005`,
- run IDs,
- `/stage.txt` or `/callback`,
- the lab server's HTTP headers,
- exact temporary filenames,
- exact downloaded text,
- server ground-truth logs.

## Acceptance criteria

```text
launcher process observed                    PASS
launcher -> PowerShell parent chain          PASS
PowerShell process observed                  PASS
PowerShell -> certutil parent chain           PASS
certutil download command observed           PASS
stage file creation observed                 PASS
certutil encode command observed             PASS
encoded file creation observed               PASS
certutil decode command observed             PASS
decoded file creation observed               PASS
certutil signer evidence available           PASS
valid signer does not suppress behavior      PASS
related outbound connection observed         PASS
correlated finding generated                 PASS
coordinator received evidence/finding        PASS
portal investigation is explainable          PASS
```

If signer, command-line, file, parentage, or network collection is not yet implemented, report the corresponding item as unsupported/not yet implemented. Do not infer a PASS from the lab runner's ground truth.

## Cleanup

By default the PowerShell runner removes its temporary artifact directory. With `-KeepArtifacts`, remove the printed directory manually after investigation. Stop the lab server with Ctrl+C.
