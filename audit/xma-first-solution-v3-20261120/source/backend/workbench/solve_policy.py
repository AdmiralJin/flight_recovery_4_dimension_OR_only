"""Versioned runtime recommendations shared by v3 and direct benchmarks."""
POLICY_VERSION = "size-aware-v1"


def recommend_time_limit(flights, candidates=0, assignment_pairs=0):
    """A budget recommendation, never a promise of feasibility or optimality."""
    flights, candidates, assignment_pairs = int(flights), int(candidates), int(assignment_pairs)
    if min(flights, candidates, assignment_pairs) < 0:
        raise ValueError("problem sizes must be nonnegative")
    tier = next((i for i, limit in enumerate((12, 50, 100, 500)) if flights <= limit), 4)
    for count, thresholds in ((candidates, (100, 1000, 5000, 20000)),
                              (assignment_pairs, (1000, 10000, 100000, 1000000))):
        tier = max(tier, next((i for i, limit in enumerate(thresholds) if count <= limit), 4))
    return {"policy_version": POLICY_VERSION, "tier": tier,
            "time_limit_seconds": (600, 1800, 3600, 7200, 14400)[tier],
            "flights": flights, "candidates": candidates, "assignment_pairs": assignment_pairs,
            "threads": 1, "mip_gap": 0.0}
