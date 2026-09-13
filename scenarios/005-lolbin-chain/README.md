# NETA-LAB-005 — System-Utility Staging Chain

## Purpose

Validate that trusted or ordinary system utilities are not automatically treated as safe when they participate in an unusual but harmless staging sequence.

The scenario is cross-platform under one immutable ID. Windows uses its original signed-utility/LOLBin semantics; Linux uses system/package provenance rather than pretending Authenticode exists on Linux.

## Controlled behavior

The staged object is deterministic inert text. It is downloaded, Base64-encoded, decoded, hash-checked, and followed by one HTTP callback. No downloaded content is executed, no persistence is created, no credentials are accessed, and no security control is changed.

Windows:

```text
cmd.exe -> powershell.exe -> certutil.exe download/encode/decode -> callback
```

Linux:

```text
bash -> curl download -> base64 encode/decode -> sha256sum validation -> curl callback
```

## Linux provenance semantics

Linux records package-manager provenance for the participating system utilities when the host can provide it. On Debian/Ubuntu this uses `dpkg-query`; on RPM-based systems it uses `rpm`. If provenance is unavailable, the lab reports it as unavailable rather than fabricating a signed/verified state.

The security rule is the same across platforms: trusted publisher identity or package/system provenance is contextual evidence, not a behavioral allowlist.

## Linux run

Start the controlled server:

```bash
python3 server/lab_http_server.py --bind 0.0.0.0 --port 18580
```

Then on the observed Linux endpoint:

```bash
./linux/run.sh <LAB-HOST> [port=18580]
```

The runner prints independent ground truth including utility paths, available package provenance, and before/after SHA-256 values.

## Windows run

Use the existing implementation under `windows/`. Windows continues to validate Authenticode signer evidence for `certutil.exe` independently from behavioral evidence.

## Expected findings

Windows may retain the more specific semantic name:

```text
SIGNED_SYSTEM_UTILITY_STAGING_CHAIN
```

The cross-platform/Linux semantic name is:

```text
SYSTEM_UTILITY_STAGING_CHAIN
```

Detection must be based on process ancestry, command-line/file activity, network evidence, and trust/provenance context. It must not depend on lab IDs, exact filenames, server paths, HTTP headers, or ground-truth logs.

## Safety and cleanup

Run only on systems you own or are explicitly authorized to test. Linux temporary artifacts are removed automatically. Stop the controlled HTTP server after the test.
