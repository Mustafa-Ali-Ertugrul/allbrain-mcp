from __future__ import annotations

from dataclasses import dataclass, field

from allbrain.domains.collaboration.workflow.models import TaskGraph, TaskNode, WorkflowStatus


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)
    dangling_nodes: list[str] = field(default_factory=list)


class DependencyEngine:
    def validate(self, graph: TaskGraph) -> ValidationResult:
        errors: list[str] = []
        cycles: list[list[str]] = []
        dangling: list[str] = []

        if not graph.nodes:
            errors.append("Graph has no nodes")
            return ValidationResult(valid=False, errors=errors)

        node_ids = set(graph.nodes.keys())
        for edge in graph.edges:
            if edge.from_id not in node_ids:
                errors.append(f"Edge references unknown from_id '{edge.from_id}'")
                dangling.append(edge.from_id)
            if edge.to_id not in node_ids:
                errors.append(f"Edge references unknown to_id '{edge.to_id}'")
                dangling.append(edge.to_id)
            if edge.from_id == edge.to_id:
                errors.append(f"Self-loop detected on node '{edge.from_id}'")
                cycles.append([edge.from_id, edge.from_id])

        # Dangling edges make _find_cycle unsafe — skip cycle check
        if not dangling:
            cycle = self._find_cycle(graph)
            if cycle:
                cycles.append(cycle)
                errors.append(f"Cycle detected: {' -> '.join(cycle)}")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            cycles=cycles,
            dangling_nodes=list(set(dangling)),
        )

    def ready_set(self, graph: TaskGraph) -> list[TaskNode]:
        ready: list[TaskNode] = []
        for node_id, node in graph.nodes.items():
            if node.status not in {WorkflowStatus.PENDING, WorkflowStatus.READY}:
                continue
            preds = graph.predecessors(node_id)
            if not preds:
                ready.append(node)
                continue
            if all(p.status == WorkflowStatus.COMPLETED for p in preds):
                ready.append(node)
        ready.sort(key=lambda n: (-n.priority, n.node_id))
        return ready

    def blocking_reason(self, graph: TaskGraph, node_id: str) -> str | None:
        node = graph.nodes.get(node_id)
        if node is None:
            return "Node not found"
        if node.status in {WorkflowStatus.COMPLETED, WorkflowStatus.RUNNING}:
            return None
        preds = graph.predecessors(node_id)
        if not preds:
            return None
        failed = [p.node_id for p in preds if p.status == WorkflowStatus.FAILED]
        blocked = [p.node_id for p in preds if p.status == WorkflowStatus.BLOCKED]
        pending = [p.node_id for p in preds if p.status in {WorkflowStatus.PENDING, WorkflowStatus.READY}]
        if failed:
            return f"Predecessor(s) failed: {', '.join(failed)}"
        if blocked:
            return f"Predecessor(s) blocked: {', '.join(blocked)}"
        if pending:
            return f"Predecessor(s) pending: {', '.join(pending)}"
        return None

    def critical_path(self, graph: TaskGraph) -> list[str]:
        node_ids = list(graph.nodes.keys())
        topo = self.topological_sort(graph)
        if not topo:
            return []

        dist: dict[str, int] = {nid: graph.nodes[nid].priority for nid in node_ids}
        prev: dict[str, str | None] = {nid: None for nid in node_ids}

        for nid in topo:
            for succ in graph.successors(nid):
                if dist[nid] + succ.priority > dist[succ.node_id]:
                    dist[succ.node_id] = dist[nid] + succ.priority
                    prev[succ.node_id] = nid

        if not dist:
            return []
        end = max(dist, key=lambda k: dist[k])
        path: list[str] = []
        cur: str | None = end
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return path

    def is_dag(self, graph: TaskGraph) -> bool:
        return self._find_cycle(graph) is None

    def topological_sort(self, graph: TaskGraph) -> list[str]:
        if not self.is_dag(graph):
            return []
        in_degree: dict[str, int] = {nid: 0 for nid in graph.nodes}
        adj: dict[str, list[str]] = {nid: [] for nid in graph.nodes}
        for edge in graph.depends_on_edges():
            if edge.from_id not in adj or edge.to_id not in adj:
                continue
            adj[edge.from_id].append(edge.to_id)
            in_degree[edge.to_id] += 1

        queue = [nid for nid, d in in_degree.items() if d == 0]
        queue.sort()
        result: list[str] = []
        while queue:
            nid = queue.pop(0)
            result.append(nid)
            for succ in sorted(adj[nid]):
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)
                    queue.sort()
        return result

    def _find_cycle(self, graph: TaskGraph) -> list[str] | None:
        white, gray, black = 0, 1, 2
        color: dict[str, int] = {nid: white for nid in graph.nodes}
        parent: dict[str, str | None] = {nid: None for nid in graph.nodes}
        adj: dict[str, list[str]] = {nid: [] for nid in graph.nodes}
        for edge in graph.depends_on_edges():
            if edge.from_id not in adj or edge.to_id not in adj:
                continue
            adj[edge.from_id].append(edge.to_id)

        def dfs(node_id: str) -> list[str] | None:
            color[node_id] = gray
            for succ in adj[node_id]:
                if color[succ] == gray:
                    cycle: list[str] = [succ]
                    cur = node_id
                    while cur != succ:
                        cycle.append(cur)
                        cur = parent[cur]
                    cycle.append(succ)
                    cycle.reverse()
                    return cycle
                if color[succ] == white:
                    parent[succ] = node_id
                    found = dfs(succ)
                    if found:
                        return found
            color[node_id] = black
            return None

        for nid in sorted(graph.nodes):
            if color[nid] == white:
                cycle = dfs(nid)
                if cycle:
                    return cycle
        return None
