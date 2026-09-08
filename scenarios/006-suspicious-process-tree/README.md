# NETA-LAB-006 — Suspicious Process Tree / Process Masquerading Chain

## Purpose

Generate a safe Windows process-only chain that looks suspicious because of **where a signed executable runs from and what it launches**, not because the executable is malicious.

The scenario copies the legitimate Windows `cmd.exe` binary into a temporary user-writable directory under a helper-style name, executes that renamed copy, and has it launch a short burst of ordinary Windows utilities.

The controlled chain is:

```text
cmd.exe test launcher
    -> powershell.exe
        -> copies C:\Windows\System32\cmd.exe
           to %TEMP%\...\windows-update-helper.exe
        -> windows-update-helper.exe
            -> whoami.exe
            -> hostname.exe
            -> ipconfig.exe /all
```

No network activity is required for the core scenario or finding.

## Why this scenario exists

NETA-LAB-004 validates a scripted download -> execute -> network chain. NETA-LAB-005 validates suspicious use of a signed LOLBin. NETA-LAB-006 isolates another EDR primitive: **process ancestry plus executable identity and path context**.

The interesting facts are deliberately contradictory:

- the copied executable is byte-for-byte the legitimate Microsoft `cmd.exe`,
- its embedded signer/original-file identity remains legitimate,
- its hash matches the system binary,
- but it executes from an unusual user-writable path under a misleading helper-style filename,
- and it immediately launches several child processes.

NETA should therefore preserve signer/hash trust evidence without treating that trust as proof that the observed execution context is safe.

## Safety boundary

This scenario is intentionally benign:

- no executable is downloaded,
- no code is injected into another process,
- no persistence is created,
- no privilege escalation is attempted,
- no credentials or secrets are collected,
- no security settings are changed,
- no network connection is required,
- child utilities only report ordinary local identity/host/network-configuration information into temporary text files,
- all temporary artifacts are removed by default.

Run it only on systems you own or are explicitly authorized to test.

## Run on Windows

From a Command Prompt at the repository root:

```cmd
scenarios\006-suspicious-process-tree\windows\launch.cmd
```

Or directly from PowerShell:

```powershell
.\scenarios\006-suspicious-process-tree\windows\run.ps1
```

To retain the temporary copied executable and child-output files for manual inspection:

```powershell
.\scenarios\006-suspicious-process-tree\windows\run.ps1 -KeepArtifacts
```

## Independent ground truth

The runner prints a compact ground-truth record containing:

- run ID,
- original `cmd.exe` path,
- copied executable path,
- SHA-256 of the original and copied executable,
- Authenticode status and signer subject,
- PE `OriginalFilename` metadata when available,
- copied executable PID,
- child commands requested,
- exit code.

The hashes must match. The copied executable path must be outside the normal Windows system directory.

These lab values exist only to validate NETA observations. Detection logic must not depend on the exact temporary filename, scenario ID, run ID, or output filenames.

## Expected NETA evidence

Required for the core PASS when the corresponding EDR capabilities exist:

- launcher process start,
- PowerShell process start,
- parent relation `cmd.exe -> powershell.exe`,
- file creation for the copied executable,
- copied executable path,
- executable SHA-256,
- process start for the renamed executable,
- parent relation `powershell.exe -> windows-update-helper.exe`,
- child process starts for the harmless utilities,
- parent relation from the renamed executable to those child utilities,
- executable signer state and signer identity,
- executable/original-file identity when available,
- correlated finding preserving the supporting process/file evidence.

Useful supporting evidence:

- first-seen executable/path state,
- user/logon identity,
- file size and timestamps,
- process command line,
- process duration/exit status.

Network, DNS, TLS, route, and TCP evidence are **not required** for this scenario.

## Expected finding

The initial semantic finding is:

```text
RENAMED_SYSTEM_BINARY_PROCESS_TREE
```

Recommended interpretation:

> A trusted system executable was observed running from a nonstandard user-writable path under a different filename and launching a short child-process chain. The binary itself may be legitimate; the execution context is unusual and merits investigation.

The finding should be driven by correlated evidence such as:

```text
trusted/original executable identity
+ nonstandard executable path/name
+ copied-file identity/hash
+ unusual parent/child relation
+ child-process burst
```

A valid Microsoft signature or a hash matching the system `cmd.exe` must not automatically suppress the finding.

## Acceptance criteria

```text
launcher process observed                    PASS
launcher -> PowerShell relation              PASS
copied executable file creation              PASS
copied executable SHA-256                    PASS
hash matches source system cmd.exe           PASS
copied executable path captured              PASS
copied executable signer state               PASS
copied executable signer identity            PASS
renamed executable process observed          PASS
PowerShell -> renamed executable relation     PASS
whoami/hostname/ipconfig children observed    PASS
renamed executable -> child relations         PASS
command lines captured                       PASS
correlated finding generated                 PASS
coordinator received evidence/finding        PASS
portal investigation is explainable          PASS
```

If a required collector is unavailable, report the corresponding item as unsupported/not yet implemented. Do not infer parentage, signer state, executable identity, hashes, or path semantics from the lab script alone.

## Cleanup

By default the runner deletes its temporary scenario directory after the copied `cmd.exe` exits. With `-KeepArtifacts`, the runner prints the retained directory so it can be inspected and then removed manually.
