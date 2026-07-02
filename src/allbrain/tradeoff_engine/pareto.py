from __future__ import annotations

from allbrain.tradeoff_engine.model import ParetoFrontier, UtilityResult


class ParetoAnalyzer:
    """Finds non-dominated candidates (Pareto front).

    A dominates B if all dimensions >= B and at least one > B.
    For safety-critical: safety-passed candidates always dominate failed ones.

    Pre-pruning (bounding box):
    1. Sort safe candidates by safety descending
    2. Track running maximum of stability/success/efficiency
    3. If a candidate is strictly below running max in all non-safety dims,
       mark it dominated without full O(n^2) pairwise comparison
    """

    @staticmethod
    def analyze(results: list[UtilityResult]) -> ParetoFrontier:
        if not results:
            return ParetoFrontier(fault_type="unknown")

        safe = [r for r in results if r.safety_pass]
        unsafe = [r for r in results if not r.safety_pass]
        for r in unsafe:
            r.dominated = True

        # Pre-pruning: bounding-box filter
        # Sort by safety descending, track running max of other dims
        safe_sorted = sorted(safe, key=lambda r: (-r.safety, -r.stability, -r.success, -r.efficiency))

        pre_pruned: list[UtilityResult] = []
        frontier_candidates: list[UtilityResult] = []

        max_stability = -1.0
        max_success = -1.0
        max_efficiency = -1.0

        for r in safe_sorted:
            # If ALL non-safety metrics are <= running max and at least one < running max
            if (
                r.stability <= max_stability
                and r.success <= max_success
                and r.efficiency <= max_efficiency
                and (r.stability < max_stability or r.success < max_success or r.efficiency < max_efficiency)
            ):
                r.dominated = True
                pre_pruned.append(r)
            else:
                frontier_candidates.append(r)
                max_stability = max(max_stability, r.stability)
                max_success = max(max_success, r.success)
                max_efficiency = max(max_efficiency, r.efficiency)

        # Full O(k^2) on remaining candidates (k << n after pre-pruning)
        dominated: list[UtilityResult] = list(pre_pruned)
        frontier: list[UtilityResult] = []

        for a in frontier_candidates:
            is_dominated = False
            for b in frontier_candidates:
                if a is b:
                    continue
                if ParetoAnalyzer._dominates(b, a):
                    is_dominated = True
                    break
            if is_dominated:
                dominated.append(a)
            else:
                frontier.append(a)

        dominated.extend(unsafe)
        return ParetoFrontier(
            fault_type=safe[0].fault_type if safe else "unknown", frontier=frontier, dominated=dominated
        )

    @staticmethod
    def _dominates(a: UtilityResult, b: UtilityResult) -> bool:
        dims = [
            ("safety", a.safety, b.safety),
            ("stability", a.stability, b.stability),
            ("success", a.success, b.success),
            ("efficiency", a.efficiency, b.efficiency),
        ]
        all_ge = all(av >= bv for _, av, bv in dims)
        any_gt = any(av > bv for _, av, bv in dims)
        return all_ge and any_gt
