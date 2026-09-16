# NETA Linux Fleet Lab

This directory implements Phase 2 of the large-scale realistic fleet roadmap. It creates many independent Linux endpoint contexts while reusing the real `neta-agent` broker/evidence/rule/finding path.

Main entrypoint:

```bash
sudo ./automation/neta-fleet-linux --help
```

See [`docs/LARGE_SCALE_SIMULATOR_PHASE2.md`](../docs/LARGE_SCALE_SIMULATOR_PHASE2.md) for architecture, enrollment, acceptance and scale instructions.

The lab randomizes behavior and scenario timing. It never directly generates a NETA finding.
