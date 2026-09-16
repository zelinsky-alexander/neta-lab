from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from fleet.model import Persona
from fleet.windows.model import WindowsEndpointState


THREAT_SCENARIOS = {"001", "002", "004", "005", "006", "007", "015", "024", "025"}


@dataclass(frozen=True)
class ScheduledScenario:
    due_offset_seconds: float
    endpoint_slot: str
    scenario_id: str
    parameters: dict[str, Any]


class WindowsScenarioScheduler:
    def __init__(self, seed: int) -> None:
        self.seed = seed

    @staticmethod
    def _weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
        choices = [(sid.zfill(3), weight) for sid, weight in weights.items() if weight > 0]
        if not choices:
            raise RuntimeError("persona has no positive Windows scenario weights")
        total = sum(weight for _, weight in choices)
        point = rng.random() * total
        current = 0.0
        for scenario_id, weight in choices:
            current += weight
            if point <= current:
                return scenario_id
        return choices[-1][0]

    def plan(self, endpoints: list[WindowsEndpointState], personas: dict[str, Persona],
             duration_seconds: float) -> list[ScheduledScenario]:
        rng = random.Random(self.seed)
        result: list[ScheduledScenario] = []
        for endpoint in sorted(endpoints, key=lambda item: item.slot):
            persona = personas[endpoint.persona_id]
            rate = persona.scenario_rate_per_hour / 3600.0
            if rate <= 0 or not persona.scenario_weights:
                continue
            offset = rng.expovariate(rate)
            while offset < duration_seconds:
                wants_threat = rng.random() < persona.threat_scenario_probability
                filtered = {
                    sid: weight for sid, weight in persona.scenario_weights.items()
                    if ((sid.zfill(3) in THREAT_SCENARIOS) == wants_threat)
                }
                scenario_id = self._weighted_choice(rng, filtered or persona.scenario_weights)
                parameters: dict[str, Any] = {}
                if scenario_id == "001":
                    parameters = {"count": rng.randint(4, 10), "interval_seconds": rng.randint(1, 4)}
                result.append(ScheduledScenario(offset, endpoint.slot, scenario_id, parameters))
                offset += rng.expovariate(rate)
        return sorted(result, key=lambda item: (item.due_offset_seconds, item.endpoint_slot, item.scenario_id))
