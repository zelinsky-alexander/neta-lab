# NETA-LAB-006 — Suspicious Process Tree / Process Masquerading Chain

## Purpose

Validate process ancestry plus executable identity/path context without requiring malicious code or network activity. The scenario is cross-platform under one immutable ID.

Windows copies the legitimate system `cmd.exe` into a temporary user-writable path under a different name and executes it. Linux performs the semantic equivalent by resolving the real system `sh` binary, copying that unchanged binary to a temporary path as `system-update-helper`, and executing the renamed copy.

## Linux chain

```text
bash launcher
  -> copy canonical system sh binary to $TMPDIR/.../system-update-helper
  -> system-update-helper
       -> id
       -> hostname
       -> uname -a
```

The source and copied executable SHA-256 values must be identical. The copied executable runs from a nonstandard user-writable path and immediately launches a short harmless child-process chain.

Linux records system/package provenance for the source binary when available through `dpkg-query` or `rpm`. This is the Linux trust context; the lab does not invent Authenticode signer semantics.

## Linux run

```bash
./linux/run.sh
```

The runner prints source/copy paths, both SHA-256 values, available package provenance, and the expected child set. Temporary files are removed automatically.

## Windows run

Use the existing implementation under `windows/`. Windows retains Authenticode signer/original-file identity as platform-specific supporting evidence.

## Expected finding

```text
RENAMED_SYSTEM_BINARY_PROCESS_TREE
```

The finding should be driven by the combination of trusted/system provenance, unchanged binary identity, unusual path/name, process ancestry, and child-process behavior. Trusted identity or package provenance must not suppress the contextual finding.

Network, DNS, TLS, route, and TCP evidence are not required for this scenario.

## Safety and cleanup

The scenario performs no download, injection, persistence, privilege transition, credential access, or security-control modification. Run only on systems you own or are explicitly authorized to test.
