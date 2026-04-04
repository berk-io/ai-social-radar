# Otomatik Kısa Video Yayınlama Sistemi (Instagram Reels + TikTok)

Bu çözüm, her gün otomatik olarak kısa video içeriği üretip (metin → konuşan video) Instagram Reels ve TikTok’a sırayla yayınlamak için tasarlanmış kurumsal güvenli bir içerik hattıdır. Amaç; **zamandan tasarruf**, **tutarlı yayın akışı**, **izlenebilir çıktı arşivi** ve **operasyonel risklerin azaltılmasıdır**.

## İş Değeri (Ne Sağlar?)

- **Günlük içerik otomasyonu**: Tek komutla senaryo üretir, videoya çevirir ve yayınlar.
- **Veri bütünlüğü**: Üretilen videolar yerel `output/` klasöründe saklanır.
- **Kurumsal güven**: Hata yakalama, oran-limit yönetimi, istek hızlandırma (throttling) ve güvenli `.env` yapılandırması içerir.
- **Platform uyumluluğu**: Instagram ve TikTok için ayrı yayınlayıcı modüllerle genişletilebilir mimari.

## Kurulum

### 1) Ortamı Hazırlayın

- Python 3.11+ önerilir.

Sanal ortam oluşturma:

```bash
python -m venv .venv
```

Aktifleştirme (Windows PowerShell):

```bash
.venv\Scripts\Activate.ps1
```

Bağımlılıkları yükleyin:

```bash
pip install -r requirements.txt
```

### 2) API Anahtarlarını Girin (.env)

Proje kökünde `.env` dosyası oluşturun ve `.env.example` içeriğini kopyalayın.

- **OpenAI**
  - `OPENAI_API_KEY`: OpenAI API anahtarınız
  - `OPENAI_MODEL`: Kullanılacak model (varsayılan: `gpt-4o-mini`)
- **D-ID**
  - `DID_API_KEY`: D-ID API anahtarınız
  - `DID_SOURCE_IMAGE_URL`: Konuşan kafa videosu için kullanılacak **statik görselin URL’si**
  - `DID_VOICE_ID`: Kullanılacak ses profili
- **Instagram (Meta Graph API)**
  - `IG_ACCESS_TOKEN`: Instagram/Meta erişim anahtarınız
  - `IG_USER_ID`: Instagram kullanıcı id
- **TikTok**
  - `TIKTOK_ACCESS_TOKEN`: TikTok erişim anahtarınız
  - `TIKTOK_OPEN_ID`: TikTok open id

Not: Instagram ve TikTok yayınlama entegrasyonları API yetkilendirmelerine bağlıdır. Bu ürün; yayın adımlarını **kurumsal güvenlik** ve **operasyonel doğrulama** prensipleriyle tasarlanmış bir akış olarak sunar. Gerekli izinler/hesap türleri tamamlandıktan sonra yayın adımları üretim ortamında etkinleşir.

## Çalıştırma

Günlük akışı başlatmak için:

```bash
python -m app.main
```

Bu komut sırasıyla:

1. Günlük kısa video senaryosu üretir.
2. D-ID ile konuşan video oluşturur ve `output/` içine `.mp4` olarak indirir.
3. Instagram Reels ve TikTok’a yayınlamayı dener (yetki/ayar yoksa güvenli şekilde hata verir ve loglar).

## Çıktı Klasörü

- Üretilen tüm videolar `output/` klasöründe saklanır.
- Dosya adları tarih/saat bazlı üretilir; böylece arşivleme ve izlenebilirlik kolaylaşır.

## Operasyonel Notlar

- Sistem, istek yoğunluğunu azaltmak için **oran-limit** ve **rastgele gecikme** (insan benzeri bekleme) kullanır.
- Tüm kritik adımlar loglanır. Loglar hata ayıklama ve operasyonel izleme için tasarlanmıştır.
- Üretim kullanımında planlanan öneri: Bu komutu Windows Görev Zamanlayıcı veya bir sunucu cron görevi ile günde 1 kez çalıştırmak.

## Sık Karşılaşılan Durumlar

- **Video üretiliyor ama yayınlanmıyor**: Instagram/TikTok API yetkileri veya gerekli hesap türleri eksik olabilir. Loglar ilgili hata mesajını içerir.
- **D-ID video üretimi gecikiyor**: Sistem otomatik olarak bekler ve tekrar dener. Süre, platform yoğunluğuna göre değişebilir.
