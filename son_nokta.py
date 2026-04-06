import os
from pathlib import Path
from app.config import load_config
from app.clients.openai_client import OpenAIClient
from app.http_utils import RateLimiter

def _load_moviepy():
    try:
        from moviepy.editor import AudioFileClip, CompositeVideoClip, TextClip, VideoFileClip
    except ImportError:
        from moviepy import AudioFileClip, CompositeVideoClip, TextClip, VideoFileClip
    return VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip

def main():
    output_dir = Path("output")
    config = load_config()
    rate_limiter = RateLimiter(requests_per_minute=60, min_jitter_seconds=0.1, max_jitter_seconds=0.5)
    
    openai = OpenAIClient(
        api_key=config.openai_api_key,
        model=config.openai_model,
        tts_model=config.openai_tts_model,
        tts_voice=config.openai_tts_voice,
        timeout_seconds=config.http_timeout_seconds,
        rate_limiter=rate_limiter
    )

    # DÜZELTME 1: "English:" yavaşlatıldı, Turkish bölümü eklendi,
    # Türkçe pangolin hecelenerek söyletiliyor (Pan . go . lin)
    narration_text = "English: - - Pangolin. - . - . - . - Turkish: Pangolin."
    new_audio_path = output_dir / "pangolin_FINAL_ses.mp3"

    print("🎙️ 1/3: Ses üretiliyor (English yavaş + Turkish heceleme)...")
    try:
        openai.synthesize_speech_to_mp3(text=narration_text, output_path=new_audio_path)
    except Exception as e:
        print(f"❌ Ses alınamadı: {e}")
        return

    mp4_files = list(output_dir.glob("*_background.mp4"))
    if not mp4_files:
        print("❌ Klasörde Kling videosu bulunamadı!")
        return

    video_file = sorted(mp4_files)[-1]
    final_output = output_dir / "MUSTERIYE_ATILACAK_PANGOLIN.mp4"

    print("🎬 2/3: Yazı %15 yukarı kaydırıldı (0.02 pozisyon)...")
    VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip = _load_moviepy()

    try:
        video_clip = VideoFileClip(str(video_file))
        audio_clip = AudioFileClip(str(new_audio_path))

        duration = float(video_clip.duration)
        video_clip = video_clip.subclipped(0, duration)

        delayed_audio = audio_clip.with_start(0.5)
        video_with_audio = video_clip.with_audio(delayed_audio)

        fs = int(video_with_audio.h * 0.08)
        font_path = "C:/Windows/Fonts/arialbd.ttf"

        safe_text = " \n \n \n \n Pangolin \n \n \n \n "

        try:
            # v2 Kütüphanesi
            text_clip = TextClip(
                text=safe_text,
                font_size=fs,
                color="white",
                stroke_color="black",
                stroke_width=3,
                font=font_path if os.path.exists(font_path) else None,
            )
            # DÜZELTME 2: 0.15'ten 0.02'ye → 15% yukarı kaydı
            text_clip = text_clip.with_position(("center", 0.02), relative=True).with_duration(duration)
        except Exception:
            # v1 Kütüphanesi
            text_clip = TextClip(
                txt=safe_text,
                fontsize=fs,
                color="white",
                stroke_color="black",
                stroke_width=3,
                font=font_path if os.path.exists(font_path) else None,
            )
            text_clip = text_clip.set_position(("center", 0.02), relative=True).set_duration(duration)

        composite = CompositeVideoClip([video_with_audio, text_clip], size=video_with_audio.size)
        composite.duration = duration

        print("⏳ 3/3: Birleştiriliyor...")
        composite.write_videofile(
            str(final_output),
            codec="libx264",
            audio_codec="aac",
            fps=video_clip.fps or 30,
            threads=4,
            logger=None
        )
        print(f"\n✅ Video hazır:\n👉 {final_output}")

    except Exception as e:
        print(f"❌ Kurgu hatası: {e}")

if __name__ == "__main__":
    main()