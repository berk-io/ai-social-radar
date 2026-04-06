from pathlib import Path
from app.media_editor import compose_word_lesson_video

# Output klasörünün yolunu belirliyoruz
output_dir = Path("output")

# Klasördeki dosyaları bulalım
mp4_files = list(output_dir.glob("*_background.mp4"))
mp3_files = list(output_dir.glob("*_speech.mp3"))

if not mp4_files or not mp3_files:
    print("❌ Output klasöründe gerekli dosyalar (mp4 ve mp3) bulunamadı!")
else:
    # En son eklenen dosyaları seç
    video_file = sorted(mp4_files)[-1]
    audio_file = sorted(mp3_files)[-1]
    
    # Yeni, birleşik dosyanın adı
    final_output = output_dir / "pangolin_kurtarildi_final.mp4"
    
    print(f"🎬 Bulunan Video: {video_file.name}")
    print(f"🎵 Bulunan Ses: {audio_file.name}")
    print("⏳ Birleştiriliyor, lütfen bekleyin...")
    
    try:
        # Az önce güncellediğimiz media_editor fonksiyonunu çağırıyoruz
        compose_word_lesson_video(
            background_video_path=video_file,
            narration_audio_path=audio_file,
            overlay_text="Pangolin", # Ekrana yazılacak kelime
            output_path=final_output
        )
        print(f"✅ Mükemmel! Kurtarılan video hazır: {final_output}")
    except Exception as e:
        print(f"❌ Birleştirme sırasında hata: {e}")