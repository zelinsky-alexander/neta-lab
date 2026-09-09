# NETA-LAB-020 — Resolver Correlation Negative Controls

Exercises three false-correlation traps: lookup with no connection, unrelated lookup near a connection, and multiple candidate resolver events before one connection.

Run `./linux/run.sh`.

Expected: no invented resolver-to-connection relation for the first two subcases; the ambiguous subcase must remain `AMBIGUOUS/UNKNOWN` rather than selecting a convenient event. No security finding is expected.
