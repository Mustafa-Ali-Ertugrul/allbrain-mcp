from __future__ import annotations

from allbrain.tradeoff_engine.model import ParetoFrontier, TradeoffResult, UtilityResult


class Selector:
    """Selects winner from Pareto frontier or utility ranking.

    Decision algorithm:
    1. CRITICAL objective'ler sağlanmazsa aday elenir.
    2. IMPORTANT objective'ler utility hesaplar.
    3. OPTIONAL objective'ler tie-breaker olur.
    """

    @staticmethod
    def select(results: list[UtilityResult], frontier: ParetoFrontier) -> TradeoffResult:
        if frontier.frontier:
            # Pick max utility from frontier
            winner = max(frontier.frontier, key=lambda r: r.utility)
        elif not results:
            return TradeoffResult(fault_type="unknown", winner=None, all_results=[], frontier=frontier)
        else:
            # Fallback: pick max utility among all, safety-passed first
            safe = [r for r in results if r.safety_pass]
            if safe:
                winner = max(safe, key=lambda r: r.utility)
            else:
                winner = max(results, key=lambda r: r.safety)

        return TradeoffResult(
            fault_type=winner.fault_type if winner else "unknown",
            winner=winner,
            all_results=results,
            frontier=frontier,
        )
