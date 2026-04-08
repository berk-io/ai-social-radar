"""Test script to generate an image-to-video from Kling and loop it with existing audio."""

import time
from pathlib import Path

from app.config import load_config
from app.clients.kling_client import KlingClient
from app.http_utils import RateLimiter
from app.media_editor import compose_word_lesson_video

def main() -> None:
    print("🚀 Sistem başlatılıyor... Ayarlar yükleniyor...")
    config = load_config()
    
    # Yolların tanımlanması
    base_output_dir = Path(r"C:\Users\berk\Desktop\py_projects\ai-social-agent\output")
    base_output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Kaynak Dosyalar
    source_image_path = Path("secilen_mandalina.jpg") 
    existing_audio_path = base_output_dir / "mandalina_ses.mp3"
    
    # 2. Üretilecek Dosyalar
    raw_kling_video_path = base_output_dir / "kling_ham_10s_video.mp4"
    final_looped_video_path = base_output_dir / "MANDALINA_FINAL_DONGULU.mp4"

    if not source_image_path.exists():
        print(f"❌ HATA: '{source_image_path.name}' bulunamadı! Lütfen resmi projenin ana klasörüne ekleyin.")
        return
        
    if not existing_audio_path.exists():
        print(f"❌ HATA: Ses dosyası ({existing_audio_path.name}) bulunamadı!")
        return

    print("✅ Dosyalar bulundu. API bağlantıları kuruluyor...")
    rate_limiter = RateLimiter(requests_per_minute=60, min_jitter_seconds=0.1, max_jitter_seconds=0.5)
    
    kling = KlingClient(
        api_key=config.kling_api_key,
        base_url=config.kling_base_url,
        model=config.kling_model,
        timeout_seconds=config.http_timeout_seconds,
        rate_limiter=rate_limiter
    )

    # AŞAMA 1: Kling'den 10 saniyelik canlandırma al
    if not raw_kling_video_path.exists():
        print("🎬 1/2: Kling Image-to-Video süreci başlatılıyor...")
        try:
            prompt = "The character blinks, breathes, and slightly moves its mouth as if talking. Subtle and natural animation. Minimal body movement."
            task_id = kling.create_image_to_video_task(image_path=source_image_path, prompt=prompt)
            
            print(f"⏳ Video işleniyor (Kling Görev ID: {task_id}). Bu işlem 5-10 dakika sürebilir, lütfen bekleyin...")
            video_url = kling.wait_for_video_url(task_id)
            
            print(f"📥 Video hazır! İndiriliyor: {video_url}")
            kling.download_video(video_url, raw_kling_video_path)
            print(f"✅ Ham 10s video başarıyla indirildi: {raw_kling_video_path.name}")
        except Exception as e:
            print(f"❌ Kling video üretimi sırasında hata: {e}")
            return
    else:
        print(f"✅ 1/2: Ham video zaten mevcut, API atlanıyor: {raw_kling_video_path.name}")

    # AŞAMA 2: Editör ile Loop (Döngü) Yapıp Birleştirme
    print("✂️ 2/2: Video ve mevcut ses birleştiriliyor (Loop atılıyor)...")
    try:
        compose_word_lesson_video(
            background_video_path=raw_kling_video_path,
            narration_audio_path=existing_audio_path,
            overlay_text="", 
            output_path=final_looped_video_path
        )
        print(f"🎉 İŞLEM TAMAM! Final video hazır: {final_looped_video_path}")
    except Exception as e:
        print(f"❌ Video birleştirme sırasında hata oluştu: {e}")

if __name__ == "__main__":
    main()