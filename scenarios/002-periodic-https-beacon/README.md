# NETA-LAB-002 — Periodic HTTPS Beacon

## Purpose

Generate repeated short outbound HTTPS connections at a predictable interval to a controlled TLS server. This validates periodic connection behavior plus TLS-related evidence where the active NETA platform supports it.

## Safety

Benign. No exploit, persistence, privilege escalation, credential access, or payload execution. The scenario uses a locally generated self-signed certificate and clients intentionally bypass certificate trust validation for this lab only.

## Create a lab certificate

From this scenario directory:

```bash
mkdir -p .lab-cert
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout .lab-cert/key.pem \
  -out .lab-cert/cert.pem \
  -days 2 \
  -subj "/CN=neta-lab.local"
```

Do not commit generated private keys or certificates.

## Start the HTTPS server

```bash
python3 ../../common/server/beacon_server.py \
  --bind 0.0.0.0 \
  --port 18443 \
  --cert .lab-cert/cert.pem \
  --key .lab-cert/key.pem
```

If clients are remote, allow TCP/18443 only as needed in the controlled lab firewall.

## Linux client

```bash
./linux/run.sh <LAB-IP> 18443
```

Optional:

```bash
./linux/run.sh <LAB-IP> 18443 12 5
```

## Windows client

```powershell
.\windows\run.ps1 -HostAddress <LAB-IP> -Port 18443
```

Optional:

```powershell
.\windows\run.ps1 -HostAddress <LAB-IP> -Port 18443 -Count 12 -IntervalSeconds 5
```

## Ground truth

Default run:

- 12 HTTPS requests
- one request approximately every 5 seconds
- same controlled TLS destination
- a fresh TLS client process/request for every iteration
- unique run ID used only for lab validation

The server prints JSON ground-truth records.

## Expected NETA evidence

Required on all supported platforms:

- outbound connection lifecycle
- correct remote endpoint
- correct process attribution
- approximately periodic timing

Platform-dependent:

- TLS session evidence
- certificate/SPKI identity
- TLS fidelity/source
- DNS evidence when a hostname is used

Lack of application-level TLS identity on a platform must be reported as unsupported or unavailable rather than fabricated.

## Expected finding

`PERIODIC_OUTBOUND_CONNECTION`

The initial behavioral finding can be the same semantic finding as NETA-LAB-001. TLS identity is additional supporting evidence, not a requirement for recognizing periodicity.

Recommended semantics:

- severity: LOW
- confidence: HIGH that periodicity exists
- malicious intent: UNKNOWN

## Success criteria

- default requests observed as expected
- process attribution correct
- direction outbound
- periodicity finding generated
- TLS evidence attached where genuinely supported
- finding delivered to coordinator
- finding visible in portal

## Cleanup

Stop client/server processes and delete `.lab-cert/`. No persistent endpoint changes are made.
