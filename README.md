# AllBrain MCP

One brain. Many agents. One shared memory.

![Version](https://img.shields.io/badge/version-0.2.1-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.12%20|%203.13-blue)
![Tests](https://img.shields.io/badge/tests-2108%20passed-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-80%25-yellowgreen)
[![Glama Score](https://glama.ai/api/mcp/servers/@aligoren/allbrain-mcp/badge)](https://glama.ai/mcp/servers/@aligoren/allbrain-mcp)

![AllBrain MCP banner](docs/images/banner.svg)

**Languages:** [English](#english) · [Türkçe](#türkçe)

---

## English

AllBrain MCP is an event-sourced memory and orchestration server for multi-agent work. It records what each agent did, reconstructs shared state, and helps the next agent continue with the right context.

### Features

- FastMCP server over stdio
- Append-only SQLite event log with stable UUIDv7 ordering
- Session-bound agent attribution
- Shared memory through `save_event()`, `list_events()`, and `resume_project()`
- Conflict detection and resolution
- Semantic intent extraction
- World, counterfactual, and scenario reasoning
- Causal graph with automatic cycle detection and weakest-edge pruning
- Counterfactual alternative generation with risk/confidence/cost pruning
- Governance pipeline with live-lock protection, escalation, and oscillation detection
- Deterministic replay from raw events
- **2108+ tests passing · 80%+ coverage**

### Architecture

![Architecture](docs/images/architecture.svg)

![Multi-agent flow](docs/images/multi-agent-flow.svg)

### Quick start

```powershell
uv run allbrain start --project . --agent codex
```

Install or refresh the MCP configuration for Codex, Claude Code, OpenCode, and Antigravity:

```powershell
.\scripts\install-mcp.ps1 -All          # Windows
./scripts/install-mcp.sh --all           # macOS / Linux
```

For isolated per-agent databases, add `--isolate`:

```powershell
.\scripts\install-mcp.ps1 -All -Isolate # Windows
./scripts/install-mcp.sh --all --isolate # macOS / Linux
```

See the [complete setup and troubleshooting guide](docs/setup.md) for client-specific verification and shared-memory configuration.

### How it works

1. Agent A records an event.
2. Agent B writes to the same project.
3. Agent C opens the project and receives the merged state.
4. Conflicts are surfaced instead of hidden.

### Reality check

AllBrain is a real MCP server with real tool calls and deterministic state replay. It does not make a model magically autonomous; some reasoning pipelines simulate execution instead of performing live actions in the outside world.

### Glama score

[![Glama Score](https://glama.ai/api/mcp/servers/@aligoren/allbrain-mcp/badge)](https://glama.ai/mcp/servers/@aligoren/allbrain-mcp)
[![Glama Server](https://img.shields.io/badge/Glama-MCP%20Server-blue)](https://glama.ai/mcp/servers/@aligoren/allbrain-mcp)

Check the [Glama profile](https://glama.ai/mcp/servers/@aligoren/allbrain-mcp) for MCP server score, tool descriptions, and compatibility report.

### Related MCP servers

AllBrain integrates with the broader MCP ecosystem. Here are related servers for complementary functionality:

| Server | Purpose |
|---|---|
| [Memory](https://glama.ai/mcp/servers/...) | Lightweight knowledge graph memory |
| [Sequential Thinking](https://glama.ai/mcp/servers/...) | Structured reasoning chains |
| [Context Manager](https://glama.ai/mcp/servers/...) | Session context persistence |

### Repository layout

- `src/allbrain/` — server, runtime, reducers, and tools
- `tests/` — tests for event-sourced workflows
- `docs/` — setup and architecture documentation
- `docs/images/` — GitHub-friendly diagrams

---

## Türkçe

AllBrain MCP, çoklu ajan çalışmaları için event-sourcing tabanlı bir ortak hafıza ve orkestrasyon sunucusudur. Her ajanın yaptığı işlemleri kaydeder, ortak durumu yeniden oluşturur ve sonraki ajanın doğru bağlamla devam etmesini sağlar.

### Özellikler

- Stdio üzerinden çalışan FastMCP sunucusu
- Kararlı UUIDv7 sıralamasına sahip, yalnızca eklemeli SQLite olay günlüğü
- Oturuma bağlı ajan kimliklendirmesi
- `save_event()`, `list_events()` ve `resume_project()` ile ortak hafıza
- Çakışma tespiti ve çözümü
- Anlamsal niyet çıkarımı
- Dünya modeli, karşı-olgusal ve senaryo tabanlı akıl yürütme
- Otomatik döngü tespiti ve en zayıf kenar budamasıyla nedensellik grafiği
- Risk/güven/maliyet eşiklerine göre karşı-olgusal alternatif budama
- Canlı kilit koruması, yükseltme ve salınım tespiti ile yönetişim hattı
- Ham olaylardan deterministik durum yeniden oynatma
- **2108+ test başarılı · %80+ kapsama**

### Mimari

![Mimari](docs/images/architecture.svg)

![Çoklu ajan akışı](docs/images/multi-agent-flow.svg)

### Hızlı başlangıç

```powershell
uv run allbrain start --project . --agent codex
```

Codex, Claude Code, OpenCode ve Antigravity için MCP yapılandırmasını kurmak veya yenilemek için:

```powershell
.\scripts\install-mcp.ps1 -All          # Windows
./scripts/install-mcp.sh --all           # macOS / Linux
```

Her ajan için ayrı veritabanı kullanmak isterseniz `--isolate` seçeneğini ekleyin:

```powershell
.\scripts\install-mcp.ps1 -All -Isolate # Windows
./scripts/install-mcp.sh --all --isolate # macOS / Linux
```

İstemciye özel doğrulama, ortak hafıza ayarları ve sorun giderme adımları için [ayrıntılı kurulum rehberine](docs/setup.md) bakın.

### Nasıl çalışır?

1. Ajan A bir olay kaydeder.
2. Ajan B aynı projeye yazar.
3. Ajan C projeyi açar ve birleştirilmiş durumu alır.
4. Çakışmalar gizlenmek yerine görünür hale getirilir.

### Gerçekçi kapsam

AllBrain, gerçek araç çağrıları ve deterministik durum yeniden oynatma özelliği bulunan gerçek bir MCP sunucusudur. Bir modeli sihirli biçimde otonom hale getirmez; bazı akıl yürütme hatları dış dünyada canlı işlem yapmak yerine yürütmeyi simüle eder.

### Depo yapısı

- `src/allbrain/` — sunucu, çalışma zamanı, reducer bileşenleri ve araçlar
- `tests/` — event-sourcing iş akışlarının testleri
- `docs/` — kurulum ve mimari belgeleri
- `docs/images/` — GitHub uyumlu diyagramlar

---

## Project status / Proje durumu

- **2108+** tests passing / **2108+** test başarılı
- **80%+** code coverage / **%80+** kod kapsama
- **MIT License**
- Stdio MCP handshake verified / Stdio MCP el sıkışması doğrulandı
- Multi-agent write, read, and conflict flows verified / Çoklu ajan yazma, okuma ve çakışma akışları doğrulandı
- Causal cycle detection + counterfactual pruning + live-lock protection active / Nedensellik döngü tespiti, karşı-olgusal budama ve canlı kilit koruması aktif
