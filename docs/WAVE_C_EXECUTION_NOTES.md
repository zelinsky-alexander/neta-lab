# Wave C execution notes

Wave C runners intentionally use only local/controlled resources.

- Resolver labs use loopback addresses and Python `socket.getaddrinfo()`.
- TLS identities are generated at run time from a temporary local CA.
- LAB-023 and LAB-025 require root only because they create an isolated network namespace/veth pair and apply `tc netem` to that temporary interface.
- LAB-031 requires the operator to provide the current NETA supporting-probe command through `NETA_SUPPORTING_TLS_PROBE_CMD`; without it, the supporting phase is reported as a capability/configuration gap.
- Generated CA keys/certificates are temporary and removed by cleanup.
