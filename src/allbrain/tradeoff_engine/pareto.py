from __future__ import annotations

from allbrain.tradeoff_engine.model import UtilityResult, ParetoFrontier


class ParetoAnalyzer:
    """Finds non-dominated candidates (Pareto front).

    A dominates B if all dimensions >= B and at least one > B.
    For safety-critical: safety-passed candidates always dominate failed ones.
    """

    @staticmethod
    def analyze(results: list[UtilityResult]) -> ParetoFrontier:
        if not results:
            return ParetoFrontier(fault_type="unknown")

        safe = [r for r in results if r.safety_pass]
        unsafe = [r for r in results if not r.safety_pass]
        for r in unsafe:
            r.dominated = True

        frontier: list[UtilityResult] = []
        dominated: list[UtilityResult] = []

        for a in safe:
            is_dominated = False
            for b in safe:
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
        return ParetoFrontier(fault_type=safe[0].fault_type if safe else "unknown",
                              frontier=frontier, dominated=dominated)

    @staticmethod
    def _dominates(a: UtilityResult, b: UtilityResult) -> bool:
        dims = [("safety", a.safety, b.safety), ("stability", a.stability, b.stability),
                ("success", a.success, b.success), ("efficiency", a.efficiency, b.efficiency)]
        all_ge = all(av >= bv for _, av, bv in dims)
        any_gt = any(av > bv for _, av, bv in dims)
        return all_ge and any_gt