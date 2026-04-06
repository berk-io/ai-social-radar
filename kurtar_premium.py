import os
from pathlib import Path

# MoviePy V2 yükleyici
def _load_moviepy():
    try:
        from moviepy.editor import AudioFileClip, CompositeVideoClip, TextClip, VideoFileClip, ColorClip
    except ImportError:
        from moviepy import AudioFileClip, CompositeVideoClip, TextClip, VideoFileClip, ColorClip
    return VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, ColorClip

def compose_premium_video(background_video_path, narration_audio_path, overlay_text, output_path):
    VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, ColorClip = _load_moviepy()
    
    try:
        video_clip = VideoFileClip(str(background_video_path))
        audio_clip = AudioFileClip(str(narration_audio_path))
        duration = float(video_clip.duration)
        video_clip = video_clip.subclipped(0, duration)
        
        # 1. Ses Gecikmesi (Video başlar, 1 saniye sonra ses girer)
        delayed_audio = audio_clip.with_start(1.0)
        video_with_audio = video_clip.with_audio(delayed_audio)
        
        # 2. G Harfini Kurtaran Yazı Ayarı
        # 2. G Harfini Kurtaran Yazı Ayarı
        fs = int(video_with_audio.h * 0.07) # Font boyutunu hafif küçülttük
        font_path = "C:/Windows/Fonts/arialbd.ttf"
        
        # HİLE BURADA: Kelimenin sonuna boşluk ve alt satır (\n) ekliyoruz ki kutu aşağı uzasın!
        safe_text = overlay_text + " \n"
        
        try:
            text_clip = TextClip(
                text=safe_text,
                font_size=fs,
                color="white",
                font=font_path if os.path.exists(font_path) else None,
            )
        except:
            text_clip = TextClip(text=safe_text, font_size=fs, color="white")

        # 3. Şık Siyah Kutu (Margin/Padding ekleyerek)
        # G harfinin kuyruğu sığsın diye yüksekliğe (h) fazladan 80 piksel pay verdik!
        bg_clip = ColorClip(size=(text_clip.w + 80, text_clip.h + 80), color=(0, 0, 0))
        bg_clip = bg_clip.with_opacity(0.55)
        
        # 4. Hizalama (Ortanın hafif üstü)
        bg_clip = bg_clip.with_position(("center", 0.35), relative=True).with_duration(duration)
        text_clip = text_clip.with_position(("center", 0.35), relative=True).with_duration(duration)

        # Hepsini birleştir
        composite = CompositeVideoClip([video_with_audio, bg_clip, text_clip], size=video_with_audio.size)
        composite.duration = duration
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        composite.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=video_clip.fps if getattr(video_clip, "fps", None) else 30,
            threads=4,
            logger=None
        )
        return output_path
        
    except Exception as e:
        print(f"Hata detayı: {e}")
        raise
    finally:
        pass # Clean-up is handled locally

# --- ÇALIŞTIRMA KISMI ---
output_dir = Path("output")
mp4_files = list(output_dir.glob("*_background.mp4"))
# DİKKAT: Az önce ürettiğimiz "kusursuz_ses" dosyasını arıyoruz!
mp3_files = list(output_dir.glob("*pangolin_kusursuz_ses.mp3"))

if mp4_files and mp3_files:
    video_file = sorted(mp4_files)[-1] # Son video (Pangolin)
    audio_file = sorted(mp3_files)[-1] # Bizim yeni ürettiğimiz kusursuz ses
    final_output = output_dir / "pangolin_ornek.mp4" # Adama atacağımız isim
    
    print("🎬 Kurgu Başlıyor (G Harfi Kurtarılıyor, Ses Ayarlandı)...")
    try:
        compose_premium_video(video_file, audio_file, "Pangolin", final_output)
        print(f"✅ Şaheser hazır, müşteriye gönderebilirsin: {final_output}")
    except Exception as e:
        print(f"❌ Kurgu hatası: {e}")
else:
    print("❌ Gerekli ses veya video bulunamadı!")