"""Latency profiles and delay sampling for async evaluation (DA-23, ADR-20)."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class LatencyProfile:
    """Latency distribution profile for policy inference."""

    name: str = "default"
    p50_ms: float = 160.0
    p95_ms: float = 190.0
    p99_ms: float = 230.0
    fixed_delay_s: float | None = None
    samples_ms: list[float] = field(default_factory=list)

    @classmethod
    def zero(cls) -> LatencyProfile:
        """Zero-latency profile for parity testing with synchronous mode."""
        return cls(name="zero", p50_ms=0.0, p95_ms=0.0, p99_ms=0.0, fixed_delay_s=0.0)

    @classmethod
    def from_file(cls, path: str | Path) -> LatencyProfile:
        """Load latency profile from a JSON file."""
        file_path = Path(path)
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return cls(
            name=data.get("name", file_path.stem),
            p50_ms=float(data.get("p50_ms", 160.0)),
            p95_ms=float(data.get("p95_ms", 190.0)),
            p99_ms=float(data.get("p99_ms", 230.0)),
            fixed_delay_s=float(data["fixed_delay_s"]) if "fixed_delay_s" in data else None,
            samples_ms=[float(x) for x in data.get("samples_ms", [])],
        )

    def sample_delay_s(self, rng: random.Random | None = None) -> float:
        """Sample an inference delay in seconds."""
        if self.fixed_delay_s is not None:
            return max(0.0, self.fixed_delay_s)

        if self.samples_ms:
            if rng is not None:
                val_ms = rng.choice(self.samples_ms)
            else:
                val_ms = random.choice(self.samples_ms)
            return max(0.0, val_ms / 1000.0)

        # Log-normal distribution fitted between p50 and p95
        if rng is None:
            rng = random.Random()

        # Simple triangular approximation around p50, p95, p99
        val_ms = rng.triangular(self.p50_ms * 0.8, self.p99_ms, self.p50_ms)
        return max(0.0, val_ms / 1000.0)
