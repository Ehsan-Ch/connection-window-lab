"""Replay synthetic transfer readiness and outbound sailing decisions."""
from dataclasses import asdict, dataclass
from random import Random
from statistics import mean

CAPS = (0, 30, 60, 90)
CUTOFF = 240
DEPARTURE = 270
RUNS = 160
PROFILES = {
    "normal": (0, 35, 0),
    "late": (30, 105, 0),
    "congested": (30, 105, 35),
}


@dataclass(frozen=True)
class Transfer:
    name: str
    inbound: str
    teu: int
    ready: int


def generate(seed, profile):
    """Minutes since the replay origin. TEU denotes twenty-foot equivalent units."""
    rng = Random(seed)
    low, high, extra = PROFILES[profile]
    transfers = []
    shared = rng.randint(0, extra)
    for i, scheduled in enumerate((65, 105, 140), start=1):
        # Common inbound delay affects all transfer lots on this vessel.
        arrival = scheduled + rng.randint(low, high)
        for lot in range(1, 5):
            teu = rng.randrange(10, 46, 5)
            ready = arrival + rng.randint(25, 95) + shared
            transfers.append(Transfer(f"I{i}-{lot}", f"I{i}", teu, ready))
    return transfers


def replay(transfers, cap):
    """Hold until all manifested lots are ready or the cap expires."""
    if cap < 0:
        raise ValueError("Hold cap must be nonnegative")
    waiting = {lot.name for lot in transfers if lot.ready > CUTOFF}
    hold = 0
    if waiting and cap:
        release = CUTOFF + cap
        # Only readiness events observed on or before the release limit are consumed.
        for lot in sorted(transfers, key=lambda lot: (lot.ready, lot.name)):
            if lot.ready <= CUTOFF:
                continue
            if lot.ready > release:
                break
            waiting.remove(lot.name)
            if not waiting:
                release = lot.ready
                break
        hold = release - CUTOFF
    total = sum(lot.teu for lot in transfers)
    missed = sum(lot.teu for lot in transfers if lot.name in waiting)
    return {"hold": hold, "cutoff": CUTOFF + hold, "departure": DEPARTURE + hold,
            "missed": missed, "connected": total - missed, "total": total,
            "missed_lots": sorted(waiting)}


def experiment():
    report = {}
    for name in PROFILES:
        cohort = []
        for seed in range(1, RUNS + 1):
            transfers = generate(seed, name)
            outcomes = {str(cap): replay(transfers, cap) for cap in CAPS}
            cohort.append((transfers, outcomes))
        summary = {}
        for cap in map(str, CAPS):
            saved = [outcomes["0"]["missed"] - outcomes[cap]["missed"] for _, outcomes in cohort]
            holds = [outcomes[cap]["hold"] for _, outcomes in cohort]
            summary[cap] = {
                "mean_missed": round(mean(outcomes[cap]["missed"] for _, outcomes in cohort), 3),
                "mean_saved": round(mean(saved), 3),
                "mean_hold": round(mean(holds), 3),
                "improved": sum(s > 0 for s in saved),
                "no_recovery_holds": sum(s == 0 and h > 0 for s, h in zip(saved, holds)),
                "teu_per_hold_hour": round(sum(saved) * 60 / sum(holds), 3) if sum(holds) else None,
            }
        # Fixed illustration. Its seed is chosen before looking at the outcomes.
        transfers, outcomes = cohort[0]
        report[name] = {"summary": summary, "example": [asdict(lot) for lot in transfers],
                        "outcomes": outcomes}
    return {"runs": RUNS, "baseline_cutoff": CUTOFF, "baseline_departure": DEPARTURE, "profiles": report}
