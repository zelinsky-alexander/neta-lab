# NETA-LAB-001 — Periodic HTTP Beacon

## Purpose

Generate repeated short outbound HTTP connections at a predictable interval. This safely emulates one behavioral characteristic associated with beaconing without performing malicious activity.

## Safety

Benign. No exploit, persistence, privilege escalation, credential access, or downloaded payload execution. Use only a server you control.

## Setup

On a controlled Linux/Windows/Python-capable server:

```bash
python3 ../../common/server/beacon_server.py --bind 0.0.0.0 --port 18080
```

If clients are on other machines, allow TCP/18080 only as needed in the lab firewall. Prefer a private/LAN address.

## Linux client

```bash
./linux/run.sh <LAB-IP> 18080
```

Optional arguments:

```bash
./linux/run.sh <LAB-IP> 18080 12 5
```

The last two values are request count and interval seconds.

## Windows client

```powershell
.\windows\run.ps1 -HostAddress <LAB-IP> -Port 18080
```

Optional:

```powershell
.\windows\run.ps1 -HostAddress <LAB-IP> -Port 18080 -Count 12 -IntervalSeconds 5
```

## Ground truth

Default run:

- 12 HTTP requests
- one request approximately every 5 seconds
- same destination host and port
- a unique run ID sent only for independent lab validation

The server prints one JSON record per request including timestamp, client, scenario, and run ID.

## Expected NETA evidence

Required:

- outbound connection lifecycle evidence
- correct remote endpoint
- correct process attribution
- approximately periodic connection timing

Optional depending on current platform capability:

- route evidence
- TCP metrics
- DNS evidence when a hostname is used

## Expected finding

`PERIODIC_OUTBOUND_CONNECTION`

Recommended initial semantics:

- severity: LOW
- confidence: HIGH that periodicity exists
- malicious intent: UNKNOWN

Interpretation should say the behavior is compatible with or resembles beacon-like communication. It must not claim confirmed malware, C2, or compromise from periodicity alone.

## Success criteria

For a default run:

- expected requests/connections: 12
- observed: 12 or a documented explanation for connection reuse/platform behavior
- process attribution: correct
- direction: outbound
- periodicity detector: fires
- finding reaches coordinator
- finding is visible in portal

## Cleanup

Stop the client loop when complete and stop the lab server. This scenario makes no persistent endpoint changes.
