"""Latency profiles and delay sampling for async evaluation (DA-23, ADR-20)."""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

from flywheel.loop.runner.rtc_log import read_rtc_log


@dataclass(frozen=True)
class LatencyProfile:
    """Latency distribution profile for policy inference."""

    name: str = "default"
    p50_ms: float = 160.0
    p95_ms: float = 190.0
    p99_ms: float = 230.0
    fixed_delay_s: float | None = None
    samples_s: list[float] = field(default_factory=list)

    @classmethod
    def zero(cls) -> LatencyProfile:
        """Zero-latency profile for parity testing with synchronous mode."""
        return cls(name="zero", p50_ms=0.0, p95_ms=0.0, p99_ms=0.0, fixed_delay_s=0.0)

    @classmethod
    def from_file(cls, path: str | Path) -> LatencyProfile:
        """Load latency profile from a JSON file."""
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"Latency profile file does not exist: {file_path}")
        data = json.loads(file_path.read_text(encoding="utf-8"))
        samples = [float(x) for x in data.get("samples_s", [])]
        if not samples and "samples_ms" in data:
            samples = [float(x) / 1000.0 for x in data["samples_ms"]]
        return cls(
            name=data.get("name", file_path.stem),
            p50_ms=float(data.get("p50_ms", 160.0)),
            p95_ms=float(data.get("p95_ms", 190.0)),
            p99_ms=float(data.get("p99_ms", 230.0)),
            fixed_delay_s=(
                float(data["fixed_delay_s"])
                if "fixed_delay_s" in data and data["fixed_delay_s"] is not None
                else None
            ),
            samples_s=samples,
        )

    def to_file(self, path: str | Path) -> Path:
        """Save profile to JSON file."""
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.name,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "fixed_delay_s": self.fixed_delay_s,
            "samples_s": self.samples_s,
        }
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return file_path

    @classmethod
    def from_log(cls, log_path: str | Path, name: str = "empirical") -> LatencyProfile:
        """Empirical profile from the request latencies of an RTC log (`rtc.jsonl`)."""
        records = read_rtc_log(Path(log_path))
        samples = sorted(r.chunk_received_s - r.observation_sent_s for r in records)
        n = len(samples)
        p50 = samples[int(n * 0.50)] * 1000.0
        p95 = samples[min(int(n * 0.95), n - 1)] * 1000.0
        p99 = samples[min(int(n * 0.99), n - 1)] * 1000.0
        return cls(
            name=name,
            p50_ms=round(p50, 2),
            p95_ms=round(p95, 2),
            p99_ms=round(p99, 2),
            samples_s=samples,
        )

    def sample_delay_s(self, rng: random.Random | None = None) -> float:
        """Sample an inference delay in seconds."""
        if self.fixed_delay_s is not None:
            return max(0.0, float(self.fixed_delay_s))

        if self.samples_s:
            picker = rng.choice if rng is not None else random.choice
            return max(0.0, float(picker(self.samples_s)))

        if self.p50_ms <= 0:
            return 0.0

        if rng is None:
            rng = random.Random()

        # Log-normal distribution fitted to p50 and p95
        mu = math.log(max(1e-4, self.p50_ms / 1000.0))
        p95_s = max(1e-4, self.p95_ms / 1000.0)
        sigma = max(1e-3, (math.log(p95_s) - mu) / 1.644853)
        return max(0.0, rng.lognormvariate(mu, sigma))
