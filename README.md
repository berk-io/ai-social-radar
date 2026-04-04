# İngilizce Kelime Öğretimi — Kısa Video Yayınlama Sistemi (Instagram Reels + TikTok)

Bu çözüm, günlük **İngilizce kelime + Türkçe karşılık** formatında kısa dikey videolar üretir; **OpenAI ile metin ve ses**, **Kling AI ile arka plan görüntüsü**, **MoviePy ile birleşik çıktı** üretir ve ardından Instagram Reels ile TikTok’a yayın akışına hazırlar. Amaç; **tutarlı eğitim içeriği**, **yerel arşiv (output/)**, **operasyonel güvenilirlik** ve **kurumsal güvenli yapılandırma**dır.

## İş Değeri (Ne Sağlar?)

- **Günlük kelime otomasyonu**: Tek komutla kelime çifti, seslendirme, arka plan videosu ve birleşik yayın dosyası üretir.
- **Veri bütünlüğü**: Ara ve nihai dosyalar `output/` altında saklanır.
- **Kurumsal güven**: Hata yakalama, oran-limit, istek hızlandırma (throttling) ve `.env` ile gizli anahtar yönetimi.
- **Platform hazırlığı**: Instagram ve TikTok için yayın modülleri genişletilebilir şekilde ayrılmıştır.

## Kurulum

### 1) Ortamı Hazırlayın

- Python 3.11+ önerilir.
- **Metin üstü yazısı (MoviePy TextClip)** için birçok kurulumda **ImageMagick** gerekir. Windows’ta metin hatası alırsanız ImageMagick kurulumunu tamamlayın veya MoviePy dokümantasyonundaki yolu yapılandırın.

Sanal ortam:

```bash
python -m venv .venv
```

Aktifleştirme (Windows PowerShell):

```bash
.venv\Scripts\Activate.ps1
```

Bağımlılıklar:

```bash
pip install -r requirements.txt
```

### 2) API Anahtarlarını Girin (.env)

Proje kökünde `.env` oluşturun; `.env.example` dosyasını kopyalayın.

- **OpenAI**
  - `OPENAI_API_KEY`: API anahtarı
  - `OPENAI_MODEL`: Sohbet modeli (varsayılan: `gpt-4o-mini`)
  - `OPENAI_TTS_MODEL`: Ses üretimi (ör. `tts-1`)
  - `OPENAI_TTS_VOICE`: Ses profili (ör. `nova`)
- **Kling AI**
  - `KLING_API_KEY`: Kling API anahtarı
  - `KLING_BASE_URL`: Varsayılan `https://api.klingapi.com`
  - `KLING_MODEL`: Örn. `kling-v2.5-turbo` (hesap/planınıza göre)
- **Instagram (Meta Graph API)** — yayın için gerekli izinlerle
  - `IG_ACCESS_TOKEN`, `IG_USER_ID`
- **TikTok** — yayın için gerekli izinlerle
  - `TIKTOK_ACCESS_TOKEN`, `TIKTOK_OPEN_ID`

## Çalıştırma

```bash
python -m app.main
```

Akış:

1. OpenAI: İngilizce kelime + Türkçe çeviri ve **TTS (.mp3)**.
2. Kling AI: Kelimeyle ilişkili **kısa arka plan videosu (.mp4)**.
3. MoviePy: Sesi videoya bağlar, **kelimeyi ortada metin olarak** ekler, **nihai .mp4** üretir.
4. Yayınlayıcılar: Instagram ve TikTok adımları (hesap/izin yapılandırmasına bağlı).

## Çıktı Klasörü

- `output/` altında zaman damgalı dosya adlarıyla `.mp3`, arka plan `.mp4` ve nihai `_final.mp4` saklanır.

## Operasyonel Notlar

- İstekler **oran-limit** ve **rastgele gecikme** ile yönetilir.
- Üretimde günlük çalıştırma için Windows Görev Zamanlayıcı veya sunucu zamanlayıcı kullanılabilir.
