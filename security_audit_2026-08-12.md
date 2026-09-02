# AllBrain MCP — Güvenlik Analiz Raporu

**Tarih:** 2026-08-12
**Hedef:** `AllBrain MCP` (allbrain-agent-runtime v1.1.0) — Python 3.13, event-sourced bellek/orchestration MCP sunucusu
**Yöntem:** Kaynak ağaç keşfi → sır/credential taraması (kod + git geçmişi) → bağımlılık taraması (pip-audit + uv.lock) → statik analiz (Bandit + manuel inceleme) → auth/API incelemesi → konfigürasyon/DB/ortam incelemesi
**Kapsam dışı:** Çalışan sistem/test ortamı; yalnızca statik inceleme yapılmıştır.

---

## 1. Yönetici Özeti

| # | Önem | Bulgu | Etki | Durum |
|---|------|-------|------|-------|
| F1 | **YÜKSEK** | GitPython 3.1.50 — 15 bilinen güvenlik açığı, en yükseği **CVSS 9.3 RCE** | Uzak kod çalıştırma (koşullu) | Doğrulanmış (uv.lock) |
| F2 | **ORTA** | cryptography 49.0.0 — CVE-2026-69247 (PYSEC-2026-3552) | Bleichenbacher oracle, PKCS#7 şifre çözme | Doğrulanmış (transitif) |
| F3 | **ORTA** | Dashboard HTTP API'sinde kimlik doğrulama yok + `Access-Control-Allow-Origin: *` | Veri sızıntısı, CSRF tarzı istekler | Doğrulanmış (kod) |
| F4 | **DÜŞÜK** | Dashboard `limit` parametresi doğrulanmamış `int()` | İstek başına hizmet kesintisi (crash) | Doğrulanmış (kod) |
| F5 | **BİLGİ** | Varsayılan agent adı sabit `"unknown"`; B311 (random) atlanmış | Sınırlı/güvenli | Değerlendirildi |

**Kritik sır sızıntısı yok.** Kodda, testlerde veya git geçmişinde gerçek API anahtarı/credential bulunamadı (yalnızca bilinçli test fixture'ları). Genel savunma katmanları (redaction, prompt-injection karantinası, path sandbox, rate limiting, parametreli SQL) sağlam bulundu.

---

## 2. Bulgular (Önem Sırasına Göre)

### F1 — YÜKSEK: GitPython 3.1.50 (15 bilinen açık, CVSS 9.3 RCE)

**Konum:**
- `uv.lock` → `gitpython==3.1.50` (doğrudan bağımlılık, specifier `>=3.1.0,<4.0`; pyproject.toml'da tanımlı)
- Kullanım: `src/allbrain/domains/memory/gitbrain/parser.py` (`Repo()`, `repo.head.commit.hexsha`, `active_branch`) ve `src/allbrain/domains/analysis/world/environment.py`

**Ayrıntı:** 3.1.50, 3.1.51–3.1.58 aralığındaki sürümlerde düzeltilen 15 güvenlik bildirimini etkiler (GHSA-2f96-g7mh-g2hx, GHSA-v396-v7q4-x2qj, GHSA-956x-8gvw-wg5v, GHSA-3rp5-jjmw-4wv2, GHSA-6p8h-3wgx-97gf, GHSA-r9mr-m37c-5fr3, GHSA-94p4-4cq8-9g67, GHSA-3f7w-8rr8-f37f, GHSA-p538-c434-8v24, GHSA-9rj7-rf2p-w77r, GHSA-4gmw-gg2m-w46p, GHSA-hh9p-6wh2-4mfc, GHSA-wvpp-8hx9-p66j, GHSA-jm78-9fvv-mhgr). En yüksek öncelikli açık **CVSS 9.3**: kısa seçenek atlama tekniği (`-u<değer>` → `--upload-pack`) ile `clone_from` üzerinden **uzak kod çalıştırma**.

**İstismar edilebilirlik değerlendirmesi (azaltıcı faktörler):**
- `parser.py` yüksek seviyeli API'yi (`Repo`, `head.commit`, `active_branch`) kullanıyor; `clone_from`/`fetch` üzerinden gelen URL/branch argümanları doğrudan ağ istemcisinden kontrol edilmiyor (proje_path client girdisinden ayrıştırılıyor).
- `_safe_git` sandbox'ı kendi argv dizisini kuruyor ve `_GIT_CONFIG_OVERRIDES` uyguluyor — bu, alt komut enjeksiyonunu kısmen sınırlar.
- Yine de açıklar **doğrudan bağımlılıkta** ve gelecekte eklenecek git uzak deposu özellikleri (remote clone/fetch) bu yüzeyi anında istismar edilebilir hale getirir.

**Düzeltme:** `gitpython` sürümünü **≥3.1.58**'e yükseltin: `uv lock --upgrade-package gitpython` + `uv sync`. Uzak repo işlemleri (clone/fetch/pull) ekleniyorsa, URL/branch değerlerinin whitelist/pattern doğrulamasından geçirilmesini zorunlu kılın.

---

### F2 — ORTA: cryptography 49.0.0 → CVE-2026-69247 (PYSEC-2026-3552)

**Konum:** `uv.lock` → `cryptography==49.0.0` — **transitif** (keyring/secretstorage/joserfc zinciri üzerinden). `src/` altında doğrudan `import cryptography` bulunmuyor (teyit edildi).

**Ayrıntı:** PKCS#7 EnvelopedData şifre çözme akışında Bleichenbacher tipi oracle; düzeltme sürümü **50.0.0**.

**Etki:** Doğrudan kod kullanmadığı için istismar yüzeyi düşük; ancak transitif bağımlılık taraması (pip-audit/CVE feed'leri) bu sürümü açık olarak işaretlemeye devam eder ve keyring akışı (credential depolama) devredeyse risk gerçektir.

**Düzeltme:** `uv lock --upgrade-package cryptography` ile **≥50.0.0**'a yükseltin; üst paketlerle (keyring/joserfc) uyumluluğu `uv sync` sonrası test edin.

---

### F3 — ORTA: Dashboard HTTP API'si — kimlik doğrulama yok + CORS `*`

**Konum:** `src/allbrain/domains/memory/ui/dashboard_server.py`
- Satır 148: `self.send_header("Access-Control-Allow-Origin", "*")` (her endpoint için sabit)
- `start_dashboard(host="127.0.0.1", port=8080)` → `HTTPServer` (std lib, TLS yok); CLI: `allbrain dashboard --host --port`
- Endpoint'ler: `/overview`, `/events`, `/graph`, `/metrics` — tamamı **kimlik doğrulamasız**, tüm olay verisini (event payload'ları, context pack özetleri) döndürüyor.

**Etki:**
- Varsayılan `127.0.0.1` bağlantısında bile aynı makinede çalışan kötü niyetli bir web sayfası, CORS `*` sayesinde `fetch('http://127.0.0.1:8080/events')` ile **tüm bellek/olay verisini okuyabilir** (tarayıcı + localhost sınırı bazı tarayıcılarda kaldırıldığı için risk gerçek).
- `--host 0.0.0.0` kullanıldığında ağdaki herkes veriye erişir; `allbrain dashboard` komutu `--host` ile her arayüze açılabilir.
- Veri, bellek sisteminin ham olay kayıtlarını içerdiği için gizlilik açısından kritik.

**Düzeltme (öneriler):**
1. Dashboard'a basit **bearer token** kimlik doğrulaması ekleyin (her oturumda üretilen rastgele token; CLI başlatırken URL'de gösterilsin).
2. CORS başlığını yalnızca izin verilen origin listesine (veya `localhost` alt kümesine) sınırlayın; `*` kaldırın.
3. `--host` için varsayılanı `127.0.0.1` koruyun, `0.0.0.0` seçiminde açık bir onay/uyarı gösterin.
4. TLS olmadan ağ üzerinden açmayı engelleyin.

---

### F4 — DÜŞÜK: Dashboard `limit` parametresi hizmet kesintisine neden olabilir

**Konum:** `dashboard_server.py:224` → `limit = int(qs.get("limit", [50])[0])`

**Ayrıntı:** `?limit=abc` gönderildiğinde `int()` `ValueError` üretir; bu işlenmediği için istek 500/bağlantı kopmasıyla sonuçlanır. Ayrıca negatif veya aşırı büyük değerler doğrulanmıyor.

**Etki:** Aynı makinede çalışan herhangi bir süreç (veya açık CORS ile bir web sayfası) endpoint'i crash ettirebilir; gerçek DoS yüzeyi düşüktür (sunucu süreci genelde ayakta kalır), ama savunma katmanında (rate limiting yapılmış) bir boşluktur.

**Düzeltme:** `limit` için aralık doğrulaması ekleyin (örn. `1–1000`), hataları try/except ile 400 yanıtına çevirin.

---

### F5 — BİLGİ: Varsayılan agent adı `"unknown"` + B311 atlaması

- Event'lerde agent tanımlanamadığında varsayılan `"unknown"` kullanılıyor (traceability/korelasyon etkisi, güvenlik etkisi yok).
- `pyproject.toml` `[tool.bandit] skips=["B311"]`: `random` modülü (güvenli olmayan PRNG) kullanımı atlanmış. Bandit çıktısının **0 bulgu** olmasının nedeni budur; projede `random` yalnızca güvenlik açısından kritik olmayan yerlerde (örn. token değil, örnekleme) kullanıldığından atlama **benign** değerlendirildi. Kimlik/oturum token'larında `secrets`/`os.urandom` kullanıldığını teyit edin (incelemede görüldü).

---

## 3. İncelenip Güvenli Bulunan Alanlar

| Alan | Konum | Değerlendirme |
|------|-------|---------------|
| Komut çalıştırma | `src/allbrain/install/__init__.py:410` | Tek `subprocess.run`, sabit argv `["uv","run","--project",repo,"python","-c",probe]`; **shell yok, kullanıcı girdisi yok** → güvenli |
| SQL enjeksiyonu | `event_repository.py` ve diğer repository'ler | Tüm sorgular SQLAlchemy parametreli; ham SQL enjeksiyon yüzeyi yok |
| Path traversal | `git.py`/`parser.py` (`canonicalize_project_path` + TOCTOU re-check) | Kapsamlı sandbox; `project_path` client girdisinden ayrıştırılıyor |
| Prompt injection | `quarantine/_prompt_rules.py` | 22 kalıp, olaylar karantinaya alınıp onayla promote ediliyor |
| Rate limiting | server ara katmanı | 1000 RPS / 60s'te 100k RPM sınırı |
| Input doğrulama | `schemas.py` `BaseInputModel` | `extra="forbid"`, derinlik/uzunluk sınırları (50 KB) |
| Gizli veri koruması | `redaction.py` + resource katmanı `sanitize_payload` | Sırlar hem depolama hem yanıt katmanında redakte ediliyor |
| Dosya izinleri | DB oluşturma | `0o600` dosya modu + `umask 0o077` |
| Sır taraması | tüm `src/`, `tests/`, git geçmişi | Gerçek sızıntı yok; yalnızca deterministik test fixture'ları |
| Ortam/anahtar dosyaları | proje kökü taraması | `.env`/`.pem`/`.key` yok; `.allbrain.db` var ama `.gitignore` kapsamında (`*.db`, `.allbrain.db*`) |

---

## 4. Düzeltme Öncelik Listesi

1. **`uv lock --upgrade-package gitpython`** → ≥3.1.58 (F1 — RCE riskini kapatır)
2. **`uv lock --upgrade-package cryptography`** → ≥50.0.0 (F2)
3. **Dashboard**: token auth + CORS kısıtı + `limit` doğrulaması (F3, F4)
4. **`uv sync`** sonrası test suite çalıştırıp regresyon kontrolü
5. Yeni git-uzak-deposu özelliği eklenecekse URL/branch whitelist doğrulaması (F1 yüzey genişlemesi)

---

## 5. Ek: Kullanılan Araçlar ve Komutlar

- Bandit (SAST): `bandit -c pyproject.toml -r src/ -ll -f json` → **0 bulgu** (ham çıktı: `bandit_report_analysis.json`)
- pip-audit: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 ./.venv/Scripts/pip-audit.exe -l` → gitpython 3.1.50 (15), cryptography 49.0.0 (1)
- Sır taraması: grep tabanlı genel + yüksek-entropi kalıpları (sk-ant-, ghp_, AIza, vs.) + `git log -p` geçmiş taraması
- Manuel inceleme: config, database, schemas, events, event_repository, decorators, resources, git, context, lifecycle_middleware, cli/main, install, parser, redaction, quarantine, dashboard_server

*Not: Bu rapor statik analize dayanır; çalışan sunucu üzerinde dinamik doğrulama (dashboard auth kontrolü vb.) yapılmamıştır.*
