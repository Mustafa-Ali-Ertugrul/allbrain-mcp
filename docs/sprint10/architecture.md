# Sprint 10 — Agent Runtime Layer + Async Executor: Mimari Tasarim Dokumani

## 1. Ozet

Sprint 10, AllBrain'i "workflow planlayan" sistemden "agent calistiran" sisteme tasiyor. Sprint 9'un workflow engine'inin altinda, gercek LLM'lerle calisan async execution katmani eklenir.

Bu sprintin ciktilari:
- **AgentDefinition**: Tum agent'larin tek bir schema ile tanimlanmasi
- **AgentRegistry**: Agent tanimlarinin merkezi kayit sistemi + auto-discovery
- **AgentAdapter Pattern**: Provider-agnostic execution contract
- **SafetyWrapper**: Cost ceiling, input sanitization, rate limiting
- **TaskQueue + WorkerPool**: Async distributed execution
- **AgentRuntime**: Workflow -> Queue -> Adapter koprusu
- **CapabilityLearner**: Execution metriklerinden otomatik capability ogrenme

## 2. Temel Tasarim Kararlari

### 2.1 Event-Sourced Single Source of Truth

Onemli karar: Workflow state bir "derived view"dir. Tek dogru kaynak event store'dur.

```text
Event Store (truth)
   |
   v
Reducer (derives state)
   |
   v
WorkflowEngine (queries state)
   |
   v
AgentRuntime (executes actions)
   |
   v
New events written back to Event Store
```

Bu karar, "state != replay(state)" riskini ortadan kaldirir.

### 2.2 Distributed-First Execution Model

Sprint 10 senkron degil, async event-driven mimari kullanir:

```text
WorkflowEngine
   |
   v
enqueue(NODE_READY)
   |
   v
TaskQueue (distributed-ready)
   |
   v
WorkerPool (N workers)
   |
   v
AgentAdapter.execute()
   |
   v
AgentExecutionEvent
   |
   v
Reducer -> next NODE_READY
```

Avantajlar:
- Worker pool scale edilebilir
- Queue-based load balancing
- Event-driven reactivity
- Distributed-ready (queue Redis/RabbitMQ ile degistirilebilir)

### 2.3 Adapter Pattern

Her provider (Claude, OpenAI, Gemini, Qwen, OpenCode CLI, Codex CLI) icin tek bir `AgentAdapter` implementasyonu. Workflow engine provider'dan habersiz.

```python
class AgentAdapter(ABC):
    def execute(self, task, context) -> SubtaskResult
    def health_check(self) -> AgentHealth
    def estimate_cost(self, task) -> float
```

### 2.4 Safety First

Her adapter cagrisi SafetyWrapper'dan gecer:
- Input sanitization (prompt injection korumasi)
- Cost ceiling (per-call ve per-workflow)
- Rate limiting
- Output validation

## 3. Bilesen Tasarimi

### 3.1 AgentDefinition

```python
@dataclass(frozen=True)
class AgentDefinition:
    id: str
    name: str
    version: str
    provider: AgentProvider
    capabilities: tuple[AgentCapability, ...]
    cost: AgentCost
    latency_profile: LatencyProfile
    max_context_tokens: int
    adapter_class: type[AgentAdapter]
    config: dict[str, Any]
    safety_limits: SafetyLimits
```

### 3.2 AgentRegistry

```python
class AgentRegistry:
    def register(self, definition: AgentDefinition) -> None
    def unregister(self, agent_id: str) -> None
    def get(self, agent_id: str) -> AgentDefinition
    def list_all(self) -> list[AgentDefinition]
    def list_by_capability(self, domain: str) -> list[AgentDefinition]
    def discover_from_env() -> list[AgentDefinition]
    def to_event(self) -> dict[str, Any]
```

### 3.3 AgentAdapter ABC

```python
class AgentAdapter(ABC):
    @abstractmethod
    def execute(self, task: dict, context: ExecutionContext) -> SubtaskResult: ...

    @abstractmethod
    def health_check(self) -> AgentHealth: ...

    @abstractmethod
    def estimate_cost(self, task: dict) -> float: ...
```

### 3.4 SafetyWrapper

```python
class SafetyWrapper:
    def __init__(self, adapter: AgentAdapter, limits: SafetyLimits): ...

    def execute(self, task, context) -> SubtaskResult:
        # 1. Sanitize input
        # 2. Check cost ceiling
        # 3. Check rate limit
        # 4. Call adapter
        # 5. Validate output
        # 6. Return result
```

### 3.5 TaskQueue

```python
class TaskQueue(ABC):
    @abstractmethod
    async def enqueue(self, item: QueueItem) -> None: ...

    @abstractmethod
    async def dequeue(self, timeout: float | None = None) -> QueueItem | None: ...

    @abstractmethod
    def qsize(self) -> int: ...


class InMemoryTaskQueue(TaskQueue):
    """Default implementation, Redis/RabbitMQ swap-ready."""
```

### 3.6 WorkerPool

```python
class WorkerPool:
    def __init__(self, queue: TaskQueue, runtime: AgentRuntime, num_workers: int = 4): ...

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def submit(self, work_item: WorkItem) -> None: ...
```

### 3.7 AgentRuntime

```python
class AgentRuntime:
    def __init__(self, registry: AgentRegistry, safety: SafetyWrapper | None = None): ...

    async def execute_subtask(
        self,
        *,
        assignment: SubtaskAssignment,
        graph: TaskGraph,
        execution_context: ExecutionContext,
    ) -> SubtaskResult: ...

    def collect_metrics(self) -> list[ExecutionMetrics]: ...
```

### 3.8 CapabilityLearner

```python
class CapabilityLearner:
    """EMA-based capability auto-learning from execution metrics."""

    def __init__(self, alpha: float = 0.2): ...

    def observe(self, agent_id: str, task: dict, metrics: ExecutionMetrics) -> None: ...

    def get_capability(self, agent_id: str, domain: str) -> float: ...

    def get_all(self, agent_id: str) -> dict[str, float]: ...
```

## 4. Klasor Yapisi

```
src/allbrain/agents/
├── __init__.py
├── definition.py        # AgentDefinition, AgentCapability, AgentCost, LatencyProfile
├── registry.py          # AgentRegistry, auto-discovery
├── adapter.py           # AgentAdapter ABC, ExecutionContext, AgentHealth
├── safety.py            # SafetyWrapper, SafetyLimits
├── runtime.py           # AgentRuntime (Workflow -> Adapter bridge)
├── metrics.py           # ExecutionMetrics, MetricsCollector
├── learner.py           # CapabilityLearner (EMA)
├── queue.py             # TaskQueue ABC + InMemoryTaskQueue
├── worker.py            # WorkerPool
└── adapters/
    ├── __init__.py
    ├── base.py          # Common utilities
    ├── mock.py          # MockAdapter (for testing)
    ├── claude.py        # Anthropic Claude
    ├── openai.py        # OpenAI GPT
    ├── gemini.py        # Google Gemini
    ├── qwen.py          # Alibaba Qwen
    ├── opencode.py      # OpenCode CLI subprocess
    └── codex.py         # Codex CLI subprocess
```

## 5. Event Modeli Genislemesi

Yeni event tipleri:
- `agent_registered`
- `agent_health_changed`
- `agent_execution_started`
- `agent_execution_completed`
- `agent_execution_failed`
- `cost_ceiling_exceeded`
- `capability_updated`
- `queue_item_enqueued`
- `queue_item_dequeued`
- `worker_started`
- `worker_stopped`

## 6. Workflow Engine Entegrasyonu

Sprint 9'un `WorkflowEngine` async execution icin genisletilir:

```python
class AsyncWorkflowEngine(WorkflowEngine):
    def __init__(self, ..., runtime: AgentRuntime | None = None, queue: TaskQueue | None = None): ...

    async def step_async(self, graph, ...) -> StepResult: ...
    async def run_async(self, graph, ...) -> WorkflowResult: ...
    async def resume_async(self, graph, completed_results, ...) -> WorkflowResult: ...
```

Mevcut sync API korunur (backward compatible).

## 7. Test Stratejisi

1. **Unit tests**:
   - `test_definition.py` - AgentDefinition validation, serialization
   - `test_registry.py` - Register, unregister, discover, conflict resolution
   - `test_adapter.py` - ABC contract, mock adapter
   - `test_safety.py` - Sanitization, cost ceiling, rate limiting
   - `test_metrics.py` - Collection, aggregation
   - `test_learner.py` - EMA updates, cold start
   - `test_queue.py` - Enqueue/dequeue, ordering, capacity
   - `test_worker.py` - Pool lifecycle, graceful shutdown
   - `test_runtime.py` - End-to-end mock execution
   - `test_async_engine.py` - Async workflow execution

2. **Integration tests**:
   - `test_async_workflow_e2e.py` - Full DAG with mock agents
   - `test_capability_learning_e2e.py` - Observe -> Update -> Re-schedule
   - `test_safety_integration.py` - Cost ceiling blocks execution

## 8. Migration Stratejisi

- Yeni `agents/` modulu mevcut koda dokunmaz
- WorkflowEngine.sync API korunur
- AsyncWorkflowEngine yeni opt-in API
- Mevcut testler (111) etkilenmemeli
- Adapter'lar lazy load (sadece kullanildiginda import)

## 9. Risk Analizi

| Risk | Olasilik | Etki | Onlem |
|------|----------|------|-------|
| API key leak | Orta | Yuksek | Config abstraction + env-only + log filter |
| Cost runaway | Orta | Yuksek | Hard ceiling per agent + per workflow |
| Adapter bug | Yuksek | Orta | Contract tests, mock-first dev |
| Provider deprecation | Orta | Orta | Adapter versioning, fallback registry |
| Cold-start latency | Yuksek | Dusuk | Pre-warm adapters, async health check |
| Event store bloat | Dusuk | Orta | Metric aggregation, snapshot integration |
| Worker pool deadlock | Dusuk | Yuksek | Timeout, circuit breaker, graceful shutdown |

## 10. Performans Hedefleri

- Queue throughput: >= 100 items/sec (in-memory)
- Worker overhead: < 5ms per task (excluding adapter)
- Cold start (registry discover): < 1s
- Async step latency: < 50ms (excluding adapter execution)
- Memory footprint: < 50MB for 1000 pending items

## 11. Sonuc

Sprint 10 tamamlandiginda AllBrain:
- Herhangi bir LLM provider ile calisabilir
- Async distributed execution'a hazir
- Cost-safe (hard ceilings)
- Capability auto-learning
- Event-sourced end-to-end (agent execution'lardan output'a kadar)

Bu, "mini orchestration framework" seviyesinden "agent operating system kernel" seviyesine gecis demek.
