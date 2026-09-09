# NETA-LAB-018 — Listener Negative Control

Regression guard against creating ordinary connection history from a bare `LISTEN` socket.

Run on observed endpoint: `./linux/run.sh [bind] [port] [idle-seconds]`. It starts a listener, leaves it idle, then accepts exactly one client connection. During the idle phase NETA may expose listener/service metadata but must not create a normal per-connection history object. After one client connects, exactly one accepted connection object is expected.
