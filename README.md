# SMSAI Prototype

Bu proje, SMS akışının ilk prototipi olarak **web chat** üzerinden çalışan bir çoklu-model soru-cevap sistemidir.

## Özellikler

- Web chat arayüzü (SMS yerine hızlı MVP kanalı)
- Classification agent:
  - dil tespiti
  - intent/domain sınıflandırma
  - karmaşıklık (low/medium/high)
- Multi-model router:
  - `fast-model-v1`
  - `multilingual-model-v1`
  - `quality-model-v2`
- Token sistemi:
  - kullanıcı bazlı limit
  - global limit
  - istek başına tahmini maliyet takibi
- Kullanım kayıtları: `GET /api/usage`

## Çalıştırma

Ek bağımlılık gerektirmez (Python 3.10+).

```bash
python app/main.py
```

Ardından:
- UI: http://127.0.0.1:8000
- Chat API: `POST /api/chat`
- Usage API: `GET /api/usage`

## Test

```bash
pytest -q
```

## Not

Bu sürüm prototiptir. Üretimde gerçek LLM sağlayıcıları, kalıcı veritabanı, oran sınırlama, kimlik doğrulama ve güvenlik kontrolleri eklenmelidir.
