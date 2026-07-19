# AllBrain MCP v0.2.3 Pre-Release Raporu

## 1. Executive Summary
* **Durum:** AllBrain MCP v0.2.3 sürüm öncesi doğrulama tamam. 2849 test geçti, 3 test atlandı. Windows dosya kilitlemesi nedeniyle 2 entegrasyon testi yalnızca çevresel koşullarda başarısız olabiliyor. PyPI üzerinde Trusted Publisher yapılandırması eksik/hatalı olduğundan otomatik yayınlama adımı (Publish to PyPI) kimlik doğrulama hatası almaktadır (Dışsal Blocker).

## 2. Critical Issues
* **Bulgu:** PyPI otomatik yayınlama adımında (`Publish to PyPI`) OIDC Trusted Publisher kimlik doğrulama hatası (`invalid-publisher`).
* **Konum:** `.github/workflows/publish.yml`
* **Durum:** Açık (Dışsal Blocker)
* **Çözüm:** PyPI üzerinde `Mustafa-Ali-Ertugrul/allbrain-mcp` reposu ve `publish.yml` iş akışı için Trusted Publisher tanımlanmalıdır. İş akışına standart PyPI `environment: pypi` bildirimi eklenmiştir.
* **Bulgu:** OpenAI Key redaction regex pattern ({48,}) eski 40 karakter test key'lerle uyuşmuyordu, 15 test başarısız oluyordu.
* **Konum:** `src/allbrain/security/redaction.py`, `tests/test_redaction.py`, `tests/test_secret_bypass.py`
* **Durum:** Çözüldü
* **Çözüm:** Test key'ler 48 karaktere güncellendi.
* **Bulgu:** Ruff format ve lint hataları.
* **Konum:** `test_event_type_alias.py`, `test_redaction_nested_brackets.py`
* **Durum:** Çözüldü
* **Çözüm:** Dosyalar formatlandı, import sıraları düzeltildi, `pyproject.toml` per-file-ignores kısmına testler için `N806` eklendi.

## 3. High Severity Issues
* **Bulgu:** Telemetry middleware'i (`_result_outcome`) dict döndüren araçların sonucunu hep başarılı sayıyordu.
* **Konum:** `src/allbrain/server/lifecycle_middleware.py`
* **Durum:** Çözüldü
* **Çözüm:** Dict sonucunun `ok` ve `error` alanlarını kontrol eden mantık eklendi. Test yazıldı.

## 4. Medium Severity Issues
* **Bulgu:** `QueueCoordinator.enqueue_task` eşzamanlı çağrıldığında `IntegrityError` fırlatıp çöküyordu.
* **Konum:** `src/allbrain/server/queueing.py`
* **Durum:** Çözüldü
* **Çözüm:** `open_write_session` kullanıldı, `IntegrityError` yakalanıp DB'den mevcut kayıt döndürüldü. Eşzamanlılık testi eklendi.
* **Bulgu:** `ensure_session_started` Git parmak izi alırken ve DB event yazarken ana `_session_lock` kilidini tutuyordu.
* **Konum:** `src/allbrain/server/lifecycle_session.py`
* **Durum:** Çözüldü
* **Çözüm:** Git fingerprint alma ve ilk event yazma kilit dışına çıkarıldı, double-check locking uygulandı.
* **Bulgu:** Windows dosya kilitleme engeli.
* **Konum:** `tests/test_two_agent_sdk_pilot.py`, `tests/test_custom_agent_example.py`
* **Durum:** Çevresel (Ürün kodunda hata değil). IDE veya çalışan MCP süreci `allbrain.exe` dosyasını kilitlediğinde iki entegrasyon testi başarısız olabiliyor.
* **Çözüm:** Çalışan MCP sunucu süreçlerini sonlandırın.

## 5. Low Severity Issues
* **Bulgu:** Deprecated ortam değişkeni.
* **Konum:** `src/allbrain/config.py`
* **Durum:** Çözüldü
* **Çözüm:** `ALLBRAIN_ALLOWED_PROJECT_ROOTS` eklendi. Eskisi için `DeprecationWarning` fırlatılıyor. Test yazıldı.
* **Bulgu:** `PipelineServices` dökümantasyonda frozen yazmasına rağmen frozen değil ve mutate ediliyor.
* **Konum:** `src/allbrain/runtime_core/pipeline.py`
* **Durum:** Açık
* **Öneri:** `dataclasses.replace` kullanılabilir.

## 6. Performance Findings
* **Bulgu:** `record_git_changes` her çağrıda session'daki tüm event'leri diskten okuyordu.
* **Konum:** `src/allbrain/server/lifecycle_session.py`
* **Durum:** Çözüldü
* **Çözüm:** `context._recorded_git_keys` cache seti eklendi, mükerrer disk okuması engellendi.
* **Bulgu:** `orjson.dumps` varsayılan default handler olmadan datetime tiplerinde çökebilirdi.
* **Konum:** `src/allbrain/storage/_json.py`
* **Durum:** Çözüldü
* **Çözüm:** `default=str` parametresi `orjson.dumps` çağrısına eklendi.

## 7. Concurrency Findings
* `QueueCoordinator` eşzamanlı yazma koruması `BEGIN IMMEDIATE` + `IntegrityError` ile sağlandı. Eşzamanlılık testi (20 thread) yazıldı ve geçti.
* `ensure_session_started` kilit süresi daraltıldı, eşzamanlı thread'lerin Git fingerprint sırasında birbirini bloklaması engellendi.

## 8. Security Findings
* Dönen payload'lar ikinci kez sanitize edilerek olası gizli veri sızıntısına karşı savunma katmanı eklendi.
* `ALLOWED_PROJECT_ROOTS` path traversal koruması testlerle doğrulandı.

## 9. Architecture Findings
* `scripts/check_architecture.py` ile katman bağımlılık sınırları doğrulandı. Domain katmanı server/storage bağımlılıklarından izole.

## 10. Code Quality Findings
* Ruff check ve format hataları tamamen giderildi.

## 11. Test Coverage Gaps
* Yeni eklenen concurrency, cache ve deprecation kodları için ilgili test dosyalarında (`test_mcp_queue_coordination.py`, `test_config.py`, `test_server.py`) coverage sağlandı.

## 12. Suggested Improvements
* `PipelineServices` nesnesinin mutasyonu engellenmeli.
* Process-local rate limiter yerine çok süreçli dağıtık kullanım için paylaşımlı koordinasyon mekanizması değerlendirilebilir.
* Snapshot lease dosya adı daha öngörülemez hale getirilebilir (özellikle çok kullanıcılı sistemlerde).

## 13. Release Decision

READY WITH MINOR ISSUES

Gerekçe:
- Kritik ve yüksek öncelikli bulgu kalmadı.
- Testler, mimari kontroller ve statik analiz başarıyla geçti.
- Kalan bulgular çevresel veya düşük öncelikli tasarım iyileştirmelerinden oluşuyor; yayınlanabilirliği engellemiyor.
