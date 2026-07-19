# AllBrain MCP v0.2.3

## 🚀 Highlights

AllBrain MCP v0.2.3 kararlılık, eşzamanlılık (concurrency), performans ve güvenlik odaklı bir sürümdür. Pre-release doğrulama sürecinde tespit edilen tüm kritik ve yüksek öncelikli sorunlar giderilmiş, kapsamlı regresyon testleriyle doğrulanmıştır.

### Öne Çıkan İyileştirmeler

* 🔒 OpenAI secret redaction testleri güncellendi ve regex uyumluluğu sağlandı.
* 🧵 QueueCoordinator eşzamanlılık (race condition) problemi giderildi.
* ⚡ Session başlangıcındaki lock contention azaltıldı.
* 📈 Git değişiklik taraması O(n) disk okumasından cache tabanlı yapıya geçirildi.
* 📊 Telemetry middleware dict sonuçlarını doğru değerlendirecek şekilde düzeltildi.
* 🛡️ `ALLBRAIN_ALLOWED_PROJECT_ROOTS` ortam değişkeni eklendi ve eski yapılandırma deprecated olarak işaretlendi.
* 💾 JSON serileştirmesinde standart dışı tipler için `default=str` desteği eklendi.

---

# 🛠 Bug Fixes

* OpenAI test key uzunluğu güncellendi.
* Ruff lint ve format sorunları giderildi.
* QueueCoordinator idempotency yarış durumu düzeltildi.
* `ensure_session_started` kilit kapsamı daraltıldı.
* `record_git_changes` performansı optimize edildi.
* `_result_outcome` telemetry değerlendirmesi düzeltildi.
* `orjson.dumps` için potansiyel `JSONEncodeError` senaryoları giderildi.

---

# ⚡ Performance

* Git event taraması cache kullanacak şekilde optimize edildi.
* Session başlangıcındaki gereksiz lock süresi azaltıldı.
* Queue yazma işlemleri daha güvenli ve verimli hale getirildi.

---

# 🔒 Security

* Secret redaction doğrulandı.
* Payload sanitization güçlendirildi.
* Path traversal koruması doğrulandı.
* Ortam değişkeni isimlendirmesi standartlaştırıldı.

---

# 🧪 Testing

Pre-release doğrulama sonuçları:

* ✅ 2849 test geçti
* ⏭️ 3 test atlandı
* ⚠️ 2 Windows entegrasyon testi yalnızca çevresel dosya kilitlemesi nedeniyle başarısız olabilir
* ✅ Ruff lint geçti
* ✅ Ruff format geçti
* ✅ Architecture validation geçti

---

# ⚠️ Known Issues

* Windows üzerinde çalışan MCP süreci `allbrain.exe` dosyasını kilitlerse iki entegrasyon testi başarısız olabilir.
* `PipelineServices` henüz immutable değildir.
* Process-local rate limiter çok süreçli dağıtık kullanım için merkezi değildir.
* Snapshot lease dosya adı gelecekte daha öngörülemez hale getirilebilir.

---

# 📊 Release Statistics

* 51 MCP Tool
* Kritik güvenlik düzeltmeleri
* Concurrency iyileştirmeleri
* Performans optimizasyonları
* Genişletilmiş regresyon testleri
* Release Readiness denetimi tamamlandı

---

## Release Status

**READY WITH MINOR ISSUES**

Gerekçe:
- Kritik ve yüksek öncelikli bulgu kalmadı.
- Testler, mimari kontroller ve statik analiz başarıyla geçti.
- Kalan bulgular çevresel veya düşük öncelikli tasarım iyileştirmelerinden oluşuyor; yayınlanabilirliği engellemiyor.