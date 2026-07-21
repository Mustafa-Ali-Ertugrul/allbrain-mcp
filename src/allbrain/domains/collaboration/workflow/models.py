from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class EdgeType(StrEnum):
    DEPENDS_ON = "depends_on"
    HANDOFF = "handoff"
    PARALLEL_GATE = "parallel_gate"


class AggregationStrategy(StrEnum):
    CONCAT = "concat"
    MERGE = "merge"
    VOTE = "vote"
    SUMMARY = "summary"


@dataclass
class TaskNode:
    node_id: str
    task_id: str
    goal: str
    kind: str = "implementation"
    status: WorkflowStatus = WorkflowStatus.PENDING
    agent_id: str | None = None
    priority: int = 3
    parent_id: str | None = None
    depth: int = 0
    result: SubtaskResult | None = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "task_id": self.task_id,
            "goal": self.goal,
            "kind": self.kind,
            "status": self.status.value,
            "agent_id": self.agent_id,
            "priority": self.priority,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "result": self.result.to_dict() if self.result else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskNode:
        return cls(
            node_id=data["node_id"],
            task_id=data["task_id"],
            goal=data["goal"],
            kind=data.get("kind", "implementation"),
            status=WorkflowStatus(data.get("status", "pending")),
            agent_id=data.get("agent_id"),
            priority=data.get("priority", 3),
            parent_id=data.get("parent_id"),
            depth=data.get("depth", 0),
            result=SubtaskResult.from_dict(data["result"]) if data.get("result") else None,
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TaskEdge:
    from_id: str
    to_id: str
    edge_type: EdgeType = EdgeType.DEPENDS_ON

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_id": self.from_id,
            "to_id": self.to_id,
            "edge_type": self.edge_type.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskEdge:
        return cls(
            from_id=data["from_id"],
            to_id=data["to_id"],
            edge_type=EdgeType(data.get("edge_type", "depends_on")),
        )


@dataclass
class SubtaskResult:
    node_id: str
    agent_id: str | None
    output: str
    artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "agent_id": self.agent_id,
            "output": self.output,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubtaskResult:
        return cls(
            node_id=data["node_id"],
            agent_id=data.get("agent_id"),
            output=data.get("output", ""),
            artifacts=list(data.get("artifacts", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class AggregatedResult:
    task_id: str
    strategy: AggregationStrategy
    outputs: list[str] = field(default_factory=list)
    merged_artifacts: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "strategy": self.strategy.value,
            "outputs": self.outputs,
            "merged_artifacts": self.merged_artifacts,
            "conflicts": self.conflicts,
            "metadata": self.metadata,
        }


@dataclass
class TaskGraph:
    nodes: dict[str, TaskNode] = field(default_factory=dict)
    edges: list[TaskEdge] = field(default_factory=list)
    root_task_id: str | None = None

    def add_node(self, node: TaskNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: TaskEdge) -> None:
        self.edges.append(edge)

    def predecessors(self, node_id: str) -> list[TaskNode]:
        pred_ids = {e.from_id for e in self.edges if e.to_id == node_id and e.edge_type == EdgeType.DEPENDS_ON}
        return [self.nodes[nid] for nid in pred_ids if nid in self.nodes]

    def successors(self, node_id: str) -> list[TaskNode]:
        succ_ids = {e.to_id for e in self.edges if e.from_id == node_id and e.edge_type == EdgeType.DEPENDS_ON}
        return [self.nodes[nid] for nid in succ_ids if nid in self.nodes]

    def depends_on_edges(self) -> list[TaskEdge]:
        return [e for e in self.edges if e.edge_type == EdgeType.DEPENDS_ON]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
            "root_task_id": self.root_task_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskGraph:
        graph = cls(
            nodes={nid: TaskNode.from_dict(n) for nid, n in data.get("nodes", {}).items()},
            edges=[TaskEdge.from_dict(e) for e in data.get("edges", [])],
            root_task_id=data.get("root_task_id"),
        )
        return graph
