# Sprint 9 — Workflow Engine: Mimari Tasarim Dokumani

## 1. Ozet

Sprint 9, AllBrain MCP'nin orkestrasyon katmanini "task secer" durumundan "subtask secer, bagimlilik motoru calistirir, hata durumunda sadece failed node'u tekrar calistirir" durumuna tasiyor.

Bu sprintin ciktilari:
- **Task Graph**: DAG temelli task graph (TaskNode, TaskEdge, TaskGraph)
- **Dependency Engine**: Döngü kontrolü, topolojik siralama, hazirlik analizi
- **Subtask Scheduler**: Task yerine subtask secebilecek SchedulerV1 evrimi
- **Result Aggregator**: Architect + Build + Reviewer gibi farkli agent ciktilarini birlestiren katman
- **Failure Recovery**: Sadece basarisiz node'un retry edilmesi, workflow'un bastan baslamamasi
- **Workflow State Machine**: PENDING → READY → RUNNING → COMPLETED / FAILED / BLOCKED

## 2. Mevcut Durum Analizi

### 2.1 Var olan bilesenler
- `TaskStateReducer`: Event stream'den task state'i olusturur
- `TaskGraphBuilder`: Task state'den node/edge listesi uretir (yalnizca gorunum)
- `SchedulerV1`: Agent capability, success_rate, load skorlarina gore task atamasi yapar
- `DeterministicScheduler`: SchedulerV1'i sarar, explicit agent override ve exclude destegi saglar
- `StateMachine` / `StateEngine`: Proje seviyesi state yonetimi
- `OrchestratedResumeEngine`: Task state, graph, assignment ve decision view'lari birlestirir

### 2.2 Eksiklikler (Sprint 9 Oncesi)
1. **Subtask soyutlamasi yok**: Task'lar atomik; icinde bir graph yok
2. **DAG calistirma motoru yok**: Bagimliliklar var ama calistirma sirasini yöneten yok
3. **Retry mekanizmasi yok**: Bir task fail olunca tum workflow yeniden baslamak zorunda
4. **Coklu agent sonuc birlestirme yok**: Paralel calisan agent sonuclari birlestirilemiyor
5. **Workflow seviyesi state machine yok**: Task seviyesinde created/assigned/started/completed/failed/blocked var ama workflow seviyesinde degil

## 3. Hedef Durum (Target Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│                      WorkflowEngine                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Scheduler  │  │  Aggregator │  │  RecoveryManager    │  │
│  │  (Subtask)  │  │  (Results)  │  │  (Retry / Resume)   │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │            │
│         └────────────────┼─────────────────────┘            │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Workflow State Machine                     │  │
│  │  PENDING → READY → RUNNING → COMPLETED                  │  │
│  │                    ↓          ↑                         │  │
│  │                 FAILED ←→ BLOCKED                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              DependencyEngine (DAG)                    │  │
│  │  - Cycle detection                                     │  │
│  │  - Topological sort                                    │  │
│  │  - Ready set calculation                               │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              TaskGraph (Data Model)                    │  │
│  │  TaskNode {id, goal, status, agent_id, subtasks[]}     │  │
│  │  TaskEdge {from, to, edge_type}                        │  │
│  │  TaskGraph {nodes, edges, root_task_id}                │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 4. Bilesen Tasarimi

### 4.1 TaskGraph (Data Layer)

**TaskNode**
```python
class TaskNode:
    node_id: str           # UUIDv7
    task_id: str           # Ust task'in ID'si (foreign key event dizisine)
    goal: str
    kind: str              # implementation, testing, review, design, ...
    status: WorkflowStatus # PENDING, READY, RUNNING, COMPLETED, FAILED, BLOCKED
    agent_id: str | None
    priority: int          # 1-5
    parent_id: str | None  # Alt task icin ust task node_id
    depth: int             # Graph derinligi (root=0)
    result: SubtaskResult | None
    retry_count: int
    max_retries: int       # default: 3
```

**TaskEdge**
```python
class TaskEdge:
    from_id: str
    to_id: str
    edge_type: EdgeType    # depends_on, handoff, parallel_gate
```

**TaskGraph**
```python
class TaskGraph:
    nodes: dict[str, TaskNode]
    edges: list[TaskEdge]
    root_task_id: str
    
    def predecessors(self, node_id: str) -> list[TaskNode]: ...
    def successors(self, node_id: str) -> list[TaskNode]: ...
    def ready_nodes(self) -> list[TaskNode]: ...  # Tum onculeri COMPLETED olanlar
    def is_dag(self) -> bool: ...
    def topological_sort(self) -> list[str]: ...
```

### 4.2 DependencyEngine

```python
class DependencyEngine:
    def validate(self, graph: TaskGraph) -> ValidationResult:
        """Dongu tespiti, bagimsiz node kontrolu"""
        
    def ready_set(self, graph: TaskGraph) -> list[TaskNode]:
        """Tum onculeri COMPLETED ve kendisi PENDING/READY olan node'lar"""
        
    def blocking_reason(self, graph: TaskGraph, node_id: str) -> str | None:
        """Bir node neden hazir degil? (FAILED predecessor, BLOCKED predecessor, vs.)"""
        
    def critical_path(self, graph: TaskGraph) -> list[str]:
        """En uzun yol (toplam priority agirlikli)"""
```

### 4.3 Workflow State Machine

```
PENDING  --(dependencies met)-->  READY
READY    --(scheduler assigns)--> RUNNING
RUNNING  --(success)-->          COMPLETED
RUNNING  --(failure)-->          FAILED
RUNNING  --(blocked by ext)-->   BLOCKED
FAILED   --(retry budget ok)-->  READY
FAILED   --(retry exhausted)-->  BLOCKED
BLOCKED  --(resolved)-->         READY
```

```python
class WorkflowStateMachine:
    def __init__(self, graph: TaskGraph) -> None: ...
    
    def transition(self, node_id: str, event: StateEvent) -> TransitionResult:
        """Gecerli ise state'i degistirir, Event olusturur"""
        
    def can_transition(self, node_id: str, target: WorkflowStatus) -> bool:
        """Gecis kurallarini kontrol eder (idempotent)"""
```

### 4.4 Subtask Scheduler (SchedulerV1 Evrimi)

Mevcut `SchedulerV1.assign_task()` task seviyesinde calisiyor. Yeni `SubtaskScheduler` subtask seviyesinde calisacak:

```python
class SubtaskScheduler:
    def __init__(self, base_scheduler: SchedulerV1 | None = None): ...
    
    def next_subtasks(
        self,
        *,
        graph: TaskGraph,
        candidate_agents: list[str],
        metrics: dict[str, dict[str, Any]],
        max_parallel: int = 3,
    ) -> list[SubtaskAssignment]:
        """
        1. DependencyEngine.ready_set(graph) ile hazir node'lari bul
        2. Her node icin SchedulerV1.score_agent() ile agent skorlari hesapla
        3. Max parallel sinirina gore en iyi (node, agent) ciftlerini sec
        4. Bitisik ve bagimsiz node'lari paralelize et
        """
```

Kritik fark: Task yerine **Subtask** seciyor. Bir task'in altinda birden fazla subtask olabilir ve bunlar paralel calistirilabilir.

### 4.5 Result Aggregator

```python
class ResultAggregator:
    def aggregate(
        self,
        *,
        parent_task_id: str,
        subtask_results: list[SubtaskResult],
        strategy: AggregationStrategy = AggregationStrategy.CONCAT,
    ) -> AggregatedResult:
        """
        Farkli agent'larin ayni parent_task altindaki subtask sonuclarini birlestirir.
        
        Stratejiler:
        - CONCAT: Sonuclari sirali birlestir (default)
        - MERGE: Ayni key'lerde son degeri al / conflict detection
        - VOTE: Ayni isi yapan N agent'in sonuclarinda oy birligi
        - SUMMARY: LLM ile ozet (Simdilik desteklenmiyor, placeholder)
        """
```

Ornek: "Implement OAuth Login" task'i icin:
- Subtask A (Architect): API Design Document
- Subtask B (Build): Backend Implementation
- Subtask C (Reviewer): Security Review Document

Aggregator, bu uc dokumani sirali veya merge edilmis sekilde dondurur.

### 4.6 Failure Recovery

```python
class RecoveryManager:
    def __init__(self, max_retries: int = 3, backoff_base: float = 2.0): ...
    
    def handle_failure(
        self,
        *,
        graph: TaskGraph,
        node_id: str,
        error: str,
    ) -> RecoveryDecision:
        """
        1. node.retry_count += 1
        2. Eger retry_count < max_retries:
              - node.status = READY
              - return RETRY(node_id, delay=backoff)
        3. Eger retry_count >= max_retries:
              - node.status = BLOCKED
              - Bagimli tum successor node'lari BLOCKED yap
              - return BLOCKED_WITH_CASCADE
        """
        
    def resume_workflow(
        self,
        *,
        graph: TaskGraph,
        completed_results: dict[str, SubtaskResult],
    ) -> TaskGraph:
        """
        Workflow'u kalindan baslatir. COMPLETED node'larin sonuclarini graph'a geri yukler.
        Hazir node'lari re-ready yapar.
        """
```

### 4.7 WorkflowEngine (Orchestrator)

```python
class WorkflowEngine:
    def __init__(
        self,
        dependency_engine: DependencyEngine | None = None,
        scheduler: SubtaskScheduler | None = None,
        state_machine: WorkflowStateMachine | None = None,
        aggregator: ResultAggregator | None = None,
        recovery: RecoveryManager | None = None,
    ): ...
    
    def create_workflow(
        self,
        *,
        task_id: str,
        goal: str,
        subtasks: list[dict[str, Any]],
        edges: list[dict[str, str]],
    ) -> TaskGraph:
        """Bir task'i subtask graph'ina donusturur"""
        
    def step(self, graph: TaskGraph, events: list[EventRead]) -> StepResult:
        """
        Tek bir orkestrasyon adimi calistirir:
        1. Event'leri apply et
        2. Ready set'i hesapla
        3. Subtask'lari schedule et
        4. COMPLETED subtask'lari aggregate et
        5. FAILED subtask'lari recovery'e yolla
        """
        
    def run(self, graph: TaskGraph) -> WorkflowResult:
        """Graph tamamlanana kadar step() cagirir (sync; istenirse async wrapper eklenebilir)"""
```

## 5. Event Modeli Genislemesi

Var olan event turlerine ek olarak:

- `subtask_created`
- `subtask_started`
- `subtask_completed`
- `subtask_failed`
- `workflow_created`
- `workflow_started`
- `workflow_completed`
- `workflow_failed`
- `result_aggregated`
- `workflow_state_changed`
- `retry_scheduled`

**Idempotency**: Her event `caused_by` ile zincirleme takip edilebilir. Retry event'leri `retry_count` icerir.

## 6. Klasor Yapisi

```
src/allbrain/
├── workflow/
│   ├── __init__.py
│   ├── models.py        # TaskNode, TaskEdge, TaskGraph, SubtaskResult
│   ├── graph.py         # DependencyEngine (DAG ops)
│   ├── state_machine.py # WorkflowStateMachine
│   ├── scheduler.py     # SubtaskScheduler
│   ├── aggregator.py    # ResultAggregator
│   ├── recovery.py      # RecoveryManager
│   └── engine.py        # WorkflowEngine
├── orchestrator/
│   ├── ...              # Mevcut kodlar korunur
│   └── workflow_bridge.py  # WorkflowEngine <-> OrchestratedResumeEngine entegrasyonu
└── events/
    └── schemas.py       # Yeni event turleri eklenecek
```

## 7. Test Stratejisi

1. **Unit tests**: Her bilesen ayri test edilir
   - `test_graph.py`: DAG validation, topological sort, ready set
   - `test_state_machine.py`: Gecis kurallari, invalid gecisler
   - `test_scheduler.py`: Subtask secimi, paralel sinirlari
   - `test_aggregator.py`: Farkli stratejilerle birlestirme
   - `test_recovery.py`: Retry, cascade blocked, resume
   - `test_engine.py`: End-to-end workflow calistirma

2. **Integration tests**: `test_workflow_integration.py`
   - OAuth Login ornegini tam calistirma (Design API → Impl Backend → Write Tests → Security Review)
   - Failure senaryosu: Node 3 fail olunca sadece Node 3 retry
   - Paralel subtask senaryosu

## 8. Rollback / Migration Plani

- Yeni `workflow/` modulu mevcut `orchestrator/` modulune dokunmaz.
- `orchestrator/workflow_bridge.py` ile secimli entegrasyon saglanir.
- Eski task event'leri (`task_created`, `task_started`, ...) ile yeni workflow event'leri (`subtask_created`, ...) birlikte calisabilir.
- Eger rollback gerekiyorsa `workflow_bridge.py` kaldirilir; mevcut orkestrasyon calismaya devam eder.

## 9. Risk Analizi

| Risk | Olasilik | Etki | Onlem |
|------|----------|------|-------|
| DAG dongu olusturma | Dusuk | Yuksek | DependencyEngine.validate() her workflow creation'da calisir |
| Retry patlamasi | Orta | Orta | Exponential backoff + max_retries siniri |
| State machine deadlock | Dusuk | Yuksek | Her adimda ready set kontrolu, BLOCKED -> READY gecisi mutlaka tetiklenir |
| Sonuc birlestirme tutarsizligi | Orta | Orta | CONCAT default, MERGE/VOTE icin conflict detection |
| Event stream buyumesi | Dusuk | Dusuk | Workflow event'leri snapshot mekanizmasi ile sikistirilabilir |
