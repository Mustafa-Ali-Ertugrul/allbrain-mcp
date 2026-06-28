# ADR: Repository → Context-Aware API Migration

## Status

**Proposed** — not yet implemented. Captured as a future refactor target.

## Context

Security Patch 1 made `project_path` a required parameter in `BrainRepository.append_event()` to prevent silent data misrouting. This changed the API surface.

## Trade-off Analysis

### Mevcut API (fully explicit)

```python
repository.append_event(
    db,
    ...,
    project_path=context.project_path,
)
```

| Avantajlar | Dezavantajlar |
|------------|---------------|
| explicit — hangi değerin gittiği belli | unutulabilir (24 call site örneğinde olduğu gibi regresyon üretebilir) |
| test etmesi kolay — mock'a parametre vermek yeterli | parametre gürültüsü oluşur |
| repository bağımsız — sadece parametre alır | |

### Önerilen API (context-aware)

```python
# Seçenek A: per-call context
repository.append_event(db, context=context, ...)

# Seçenek B: constructor context
repository = BrainRepository(context)
repository.append_event(db, ...)
```

| Avantajlar | Dezavantajlar |
|------------|---------------|
| project isolation garanti olur — context içeride çekilir, unutma riski sıfır | repository artık `BrainContext`'e bağımlı hale gelir |
| call site sadeleşir — `project_path` satırı kaybolur | katmanlar biraz daha birbirine yaklaşır |
| yeni ambient field eklenirse çağrıcı değişmez | büyük çaplı migration gerekir |

## Signal

> *"repository.append_event artık 'context-aware API' değil, 'fully explicit API'"*

Bu bir **mimari sinyal**:
- **Coupling increases** — her call site `project_path`'i bilmek zorunda
- **Call surface widens** — yeni ambient field'lar parametre listesini büyütür
- **Error risk persists** — sessiz hata → `TypeError`'a evrildi ama hata riski sıfırlanmadı

## Consequences

Implementation of either "context as parameter" or "context in constructor" would produce:

| (+) Positive | (-) Negative |
|-------------|--------------|
| `project_path` unutulamaz — regresyon türü kapanır | repository artık `BrainContext`'e bağımlı hale gelir |
| çağrı yüzeyi küçülür — her `append_event` çağrısından `project_path=` satırı kaybolur | katmanlar arası mesafe azalır (repository → context dependency) |
| güvenlik varsayımları repository içine taşınır — ambient field'lar tek noktadan yönetilir | test helper'larının (`make_context`, mock setup) güncellenmesi gerekir |
| yeni ambient field (tenant, request_id, vs.) eklenirse 0 çağrıcı değişir | migration anında 24+ call site birden değişir — code review yükü |

## Trigger Conditions

Bu ADR **şu anda uygulanmıyor**. Aşağıdaki durumlardan **herhangi biri** gerçekleştiğinde uygulamaya alınmalıdır:

1. **3 veya daha fazla yeni repository metodu eklenirse** — her biri `project_path` parametresi taşımak zorunda kalır, gürültü katlanır
2. **`project_path` parametresi 20+ yerde kullanılmaya devam ederse** — mevcut durum zaten bu eşikte; yeni bir metot eklendiğinde aşılır
3. **Yeni bir güvenlik regresyonu oluşursa** — yani biri yine `project_path`'i unutup sessiz hataya yol açarsa
4. **Repository'e tenant_id, request_id, user_id gibi yeni bir ambient field eklenme ihtiyacı doğarsa** — bu, context yaklaşımının getirisini katlar

Bu koşullar sağlanana kadar mevcut explicit API korunur: çalışıyor, test coverage var, anlaşılması kolay.

## Proposed Solution

Make `BrainRepository` accept a `BrainContext` (or a dedicated `StorageContext`) so it can extract ambient fields internally:

```python
class BrainRepository:
    def append_event(self, db, *, context: BrainContext, session_id, type, payload, ...):
        project_path = context.project_path  # guaranteed present, never forgotten
        ...
```

Or, if the repository should hold per-request state:

```python
class BrainRepository:
    def __init__(self, db, context: BrainContext):
        self.db = db
        self.context = context

    def append_event(self, *, session_id, type, payload, ...):
        project_path = self.context.project_path
        ...
```

## When to Execute

Not now. Rationale:
1. Current explicit pattern is correct and has test coverage (79 tests passing)
2. Changing 24+ call sites on the same branch risks merge conflicts with other work
3. The decision should be made holistically — if other `BrainRepository` methods (`list_events`, `get_state`, etc.) also become context-aware, the migration should be coordinated

## How to Execute (future PR)

1. Add `context: BrainContext` parameter to `BrainRepository.append_event()` and friends
2. Remove `project_path` from each method's explicit parameter list
3. Update all callers to pass `context` instead of `project_path`
4. Remove now-unused `project_path = context.project_path` lines in `_impl` functions
5. Update `append_selection_decision`, `_publish_scenario_events`, `_publish_foresight_events` helpers
6. Full test suite run — no functional change expected

## Related

- Security Patch 1 (commit `9e3a067`): made `project_path` required in `append_event`
- Regresyon fix (commit `d972880`): fixed 24 missing `project_path=` call sites
- Security Regression Suite: 79 tests covering all `_impl` functions
