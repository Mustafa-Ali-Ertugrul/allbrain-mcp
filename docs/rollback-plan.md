# AllBrain MCP v0.2.3 Sürüm Geri Dönüş (Rollback) Planı ve İzleme Yönergesi

Bu doküman, v0.2.3 sürümünün yayına alınmasından sonra olası bir kararsızlık durumunda güvenli bir şekilde v0.2.2 sürümüne geri dönme (rollback) adımlarını ve ilk 72 saatlik izleme planını detaylandırır.

## 1. Geri Dönüş (Rollback) Prosedürü

### Adım 1: Git Tag ve Release Geri Alma
Yerel ve uzak etiketleri geri çekmek için aşağıdaki komutları uygulayın:
```bash
# Yerel etiketi sil
git tag -d v0.2.3

# Uzak etiketi sil
git push --delete origin v0.2.3

# GitHub Release sil
gh release delete v0.2.3 --yes
```

### Adım 2: Önceki Sürüme Dönüş (Downgrade)
Çalışan sürümü v0.2.2'ye geri çekmek için:
```bash
# v0.2.2 tagine dön
git checkout v0.2.2

# Bağımlılıkları senkronize et
uv sync --group dev
```

### Adım 3: Veritabanı Uyumluluğu (Alembic Downgrade)
v0.2.3 ile v0.2.2 arasında veritabanı şema değişikliği yapılmamıştır. Bu nedenle veritabanı şeması geriye dönük uyumludur. Herhangi bir Alembic downgrade komutuna ihtiyaç duyulmaz. Olası bir veri bozulması durumuna karşı yedekten geri dönmek için:
```bash
# Yedek veritabanını geri yükle
cp ~/.allbrain/allbrain.db.bak-<timestamp> ~/.allbrain/allbrain.db
```

---

## 2. Sürüm Sonrası İzleme Planı (Post-Release Monitoring)

Sürüm yayına alındıktan sonraki ilk 72 saat boyunca aşağıdaki metrikler ve loglar takip edilecektir:

1. **Crash Oranı:** Sunucu stdio süreçlerinin beklenmedik şekilde sonlanma sıklığı.
2. **Tool Hata Oranı:** Telemetry loglarında `ok=False` olan araç çağrılarının toplam çağrılara oranı.
3. **Queue Başarısızlıkları:** `QueueItemRecord` tablolarında `state="failed"` durumuna düşen veya lease süresi dolan (`LEASE_EXPIRED`) kayıtların izlenmesi.
4. **Replay Hataları:** `EventReplayEngine` üzerinden çalıştırılan geçmiş replayer çağrılarının hata sıklığı.
5. **WAL Dosyası Büyümesi:** SQLite WAL modunun dosya boyutu (`allbrain.db-wal` dosyasının 100MB sınırını aşmaması kontrolü).
6. **Bellek Kullanımı:** Uzun süren oturumlarda bellek sızıntısı (memory leak) kontrolü.
7. **Ortalama Tool Latency:** Her araç için `duration_ms` değerlerinin 200ms altında seyretmesi.
