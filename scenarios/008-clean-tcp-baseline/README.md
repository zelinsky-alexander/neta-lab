# NETA-LAB-008 — Clean TCP Baseline

Known-good transport baseline with stable endpoint/route and sufficiently long connections for TCP metrics. Expected threat finding: none.

Server: `python3 ../../common/server/tcp_lab_server.py --bind 0.0.0.0 --port 18448 --connections 5 --scenario NETA-LAB-008`

Linux: `./linux/run.sh <LAB-IP> 18448`

Expected evidence: lifecycle, process, RTT, RTT variance, retransmissions, route and endpoint. Expected assurance after baseline acceptance: `Performance: NORMAL`; trust is `STABLE` only when trust evidence is part of the accepted baseline.
