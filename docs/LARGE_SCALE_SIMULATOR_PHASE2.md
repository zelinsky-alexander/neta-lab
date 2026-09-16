# Large-Scale Simulator — Phase 2 Linux Fleet

Branch: `large-scale-simulator`

## Purpose

Phase 2 turns the Phase-1 `neta-agent` sensor broker into a realistic Linux fleet host. It creates persistent endpoint slots and runs the real broker-mode NETA agent in isolated Linux network/cgroup/hostname contexts. Randomness selects **behavior**, never findings.

The target progression remains:

```text
3 -> 10 -> 50 -> 100 -> 250 -> 500 Linux endpoints
```

Do not progress to the next size until the 3-endpoint isolation acceptance passes and the current level is stable.

## Implemented

- cgroup-v2 subtree per endpoint;
- Linux network namespace per endpoint;
- veth pair per endpoint attached to a dedicated `neta-sim0` bridge;
- real per-endpoint IPv4 address and route;
- `/etc/netns/<name>/resolv.conf` DNS configuration applied through `ip netns exec`;
- persistent UTS namespace/hostname keeper per endpoint;
- automatic kernel network-namespace inode discovery;
- automatic kernel cgroup ID discovery from the cgroup-v2 inode;
- automatic construction of Phase-1 broker `--map SLOT:NETNS_INODE:CGROUP_ID` arguments;
- persistent DHCP-like IP leases with explicit rotation on endpoint restart;
- persistent endpoint personas;
- real per-endpoint NETA SQLite database;
- real per-endpoint fleet state directory;
- production `neta-agent fleet enroll` integration for unique AgentId/certificate/key/sequence state;
- one real broker-mode `neta-agent observe --all` process per endpoint;
- seeded, replayable scenario planning;
- execution of existing `NETA-LAB-*` Linux behavior scripts inside the endpoint context;
- independent JSONL ground truth with expected evidence/finding metadata;
- restart with stable identity and optional IP change;
- cleanup and host-recovery path that preserves persona/lease/database/enrollment state;
- health/status reporting;
- fixed three-endpoint isolation acceptance harness;
- non-root deterministic unit tests for lease/persona/scheduler/ground-truth logic.

## Important process-isolation boundary

Phase 1 intentionally uses the simulator host PID namespace. Phase 2 therefore isolates processes by **dedicated cgroup**, not by creating a separate PID namespace that the current broker cannot safely remap.

This is deliberate: a separate PID namespace today would make the host eBPF PID identity differ from the PID visible to the broker-mode agent. NETA must not fabricate or guess that mapping. Network namespaces, cgroups, UTS hostnames, sockets, IP addresses, state, databases, AgentIds and certificates are independent. PID-namespace remapping remains a later sensor capability.

## Persistent state

Default root:

```text
/var/lib/neta-lab/fleet/default/
  fleet.json
  leases.json
  broker.log
  ground-truth/
    runs.jsonl
    lifecycle.jsonl
  endpoints/
    lnx-0001/
      endpoint.json
      persona.json
      identity/
        identity.conf
        agent.key
        agent.crt
        fleet-ca.crt
        sequence
      neta.db
      ground-truth.jsonl
      logs/
      scenarios/
```

The `identity/` contents are created by the production NETA enrollment command, not by the lab.

Disposable runtime state lives under `/run/neta-lab/fleet/default/` and cgroups under `/sys/fs/cgroup/neta-lab/default/`.

## Endpoint identity versus IP

The endpoint's AgentId, key/certificate, persona and SQLite history persist. The IP lease can change independently.

```text
lnx-0042
AgentId/certificate/persona: unchanged
10.70.17.83 -> restart --rotate-ip -> 10.70.203.41
```

The network namespace remains stable during an in-place simulated endpoint restart so the running sensor broker's netns/cgroup attribution map remains valid.

## Prerequisites

Linux fleet operations require root and:

- cgroup v2;
- `ip` / iproute2;
- `nsenter` and `unshare` from util-linux;
- `hostname`;
- Python 3;
- `curl` for NETA-LAB-001 / acceptance;
- a Phase-1 `neta-agent` binary from the matching `large-scale-simulator` branch.

No Python package dependency is added; the orchestrator uses the Python standard library and existing OS tools.

### Optional NAT egress

Local bridge scenarios need no firewall change. For endpoints that must reach a public coordinator or Internet service, opt in explicitly:

```bash
sudo ./automation/neta-fleet-linux --enable-nat ... up --count 3 ...
```

This requires `iptables` and `sysctl`. The lab adds only tagged rules for the simulator subnet/bridge: outbound MASQUERADE, bridge-originated forwarding, and established/related return traffic. It records whether it changed `net.ipv4.ip_forward` and restores that value on `down`. NAT is disabled by default so a local lab does not silently alter host firewall/forwarding state.

## Configuration

Default file:

```text
fleet/config/linux-default.json
```

For a source checkout where `neta-lab` and `neta-agent` are siblings, for example:

```bash
sudo ./automation/neta-fleet-linux \
  --agent ../neta-agent/build/neta-agent \
  --allow-unenrolled \
  up --count 3
```

`--allow-unenrolled` is only for local sensor/isolation work. It does not demonstrate coordinator NAP/mTLS identity.

## Real enrollment

Supply one unused coordinator enrollment token per endpoint. The token file can be either:

```json
{
  "lnx-0001": "one-time-token-1",
  "lnx-0002": "one-time-token-2",
  "lnx-0003": "one-time-token-3"
}
```

or an array whose order matches `lnx-0001`, `lnx-0002`, ... . Tokens are read but never copied into endpoint metadata or ground truth.

```bash
sudo ./automation/neta-fleet-linux \
  --agent ../neta-agent/build/neta-agent \
  up --count 3 \
  --coordinator https://coordinator.example:8443 \
  --fleet-ca /etc/neta/fleet-ca.crt \
  --fleet-id fleet-large-scale-lab \
  --token-file /root/neta-enrollment-tokens.json
```

Each enrollment command runs from the endpoint's own network namespace/cgroup/hostname context. The resulting identity is the normal NETA identity used by `FleetClient` and NAP/mTLS.

## Running a scenario

The scheduler executes the existing scenario implementation; it does not create findings.

```bash
sudo ./automation/neta-fleet-linux scenario \
  --slot lnx-0002 \
  --scenario 001 \
  --parameters '{"count":6,"interval_seconds":1}'
```

Phase 2 auto-wires local controlled peers for Linux scenarios `001`, `008`, `014`, and `015`. Other existing scenarios can be invoked with explicit `parameters.args` when their required controlled infrastructure is available.

Ground truth records include:

- run ID;
- endpoint slot;
- AgentId when enrolled;
- tenant/persona metadata;
- scenario ID/version;
- start/end timestamps;
- selected parameters;
- expected evidence types parsed from `expected.yaml`;
- expected finding type when declared;
- placeholders for actual observed evidence and actual finding;
- command result.

Actual NETA evidence/findings are deliberately not synthesized by the lab. A later validation pass can append `scenario_validation` records.

## Seeded scheduler

Personas live under `fleet/personas/`. They define role/activity and scenario rates/weights. The scheduler uses the fleet seed, so a given fleet/persona set produces the same plan.

```bash
sudo ./automation/neta-fleet-linux schedule --duration 3600
```

Most persona weights favor benign baseline/short-connection activity. Threat-like selections are deliberately rare.

## Restart / DHCP-like IP rotation

```bash
sudo ./automation/neta-fleet-linux restart --slot lnx-0002 --rotate-ip
```

This stops and restarts the real NETA runtime while preserving its state directory, AgentId and certificate. The endpoint receives a new persistent lease generation and the route/address are changed in place.

## Health

```bash
sudo ./automation/neta-fleet-linux status
```

Health checks broker state plus, per endpoint:

- real agent PID;
- UTS keeper PID;
- netns presence;
- cgroup presence;
- expected versus observed IP;
- enrollment presence;
- SQLite size.

## Cleanup and recovery

Normal cleanup removes only disposable kernel/runtime state:

```bash
sudo ./automation/neta-fleet-linux down
```

Personas, leases, identities, ground truth and databases remain.

Recreate disposable state after a crash/host restart:

```bash
sudo ./automation/neta-fleet-linux recover --count 3 [enrollment options]
```

Delete everything only when explicitly requested:

```bash
sudo ./automation/neta-fleet-linux down --purge-state
```

## Isolation acceptance

Before scaling beyond three endpoints:

```bash
sudo ./automation/neta-fleet-linux \
  --agent ../neta-agent/build/neta-agent \
  --allow-unenrolled \
  acceptance --count 3
```

For the full NAP/mTLS form, omit `--allow-unenrolled` and supply enrollment options.

The harness:

1. creates exactly three independent endpoint environments;
2. verifies unique netns and cgroup kernel identities;
3. starts one host sensor broker and three real broker-mode agents;
4. runs NETA-LAB-001 only from `lnx-0002` to a controlled server on the simulator bridge;
5. queries each endpoint's real NETA SQLite `connections` table;
6. requires the target connection in `lnx-0002` and zero matching target connections in `lnx-0001` / `lnx-0003`;
7. requires unique AgentIds when enrollment is enabled;
8. persists an acceptance report and cleans disposable runtime state.

If this fails, do not scale the fleet.

## Scale progression

Run the same deployment at:

```text
3
10
50
100
250
500
```

At each stage inspect endpoint health, simulator CPU/RAM, process count, broker logs/queue behavior, database growth and coordinator load before increasing the count.

## Safety

All scheduled scenarios remain the existing benign NETA Lab behaviors and controlled services. The fleet scheduler does not add exploit payloads, credential access, persistence mechanisms or destructive behavior. Run it only on hosts and coordinator infrastructure you own or are explicitly authorized to test.
