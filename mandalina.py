import os
from pathlib import Path
from app.config import load_config
from app.clients.openai_client import OpenAIClient
from app.clients.kling_client import KlingClient
from app.http_utils import RateLimiter

def _load_moviepy():
    try:
        from moviepy.editor import AudioFileClip, CompositeVideoClip, VideoFileClip, concatenate_videoclips
    except ImportError:
        from moviepy import AudioFileClip, CompositeVideoClip, VideoFileClip, concatenate_videoclips
    return VideoFileClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips

def main():
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
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

    kling = KlingClient(
        api_key=config.kling_api_key,
        base_url=config.kling_base_url,
        model=config.kling_model,
        timeout_seconds=config.http_timeout_seconds,
        rate_limiter=rate_limiter
    )

    narration_text = (
        "Merhaba çocuklar! Ben bir mandalinayım! "
        "Biliyor musunuz? Bana İngilizcede... MANDARIN derler! "
        "Hadi söyleyelim: MANDARIN. - . - . - "
        "Süper! "
        "Mandalina bir meyvedir. Meyvenin İngilizcesi: FRUIT. "
        "Hadi söyle: FRUIT. - . - . - "
        "Harikasınız! "
        "Ben turuncuyum! Turuncunun İngilizcesi: ORANGE. "
        "Söyle bakalım: ORANGE. - . - . - "
        "Çok iyi gidiyorsunuz! "
        "Hadi birlikte söyleyelim: MANDARIN. FRUIT. ORANGE. - . - . - "
        "Ben mandalinayım! Sen de harikasın! Görüşürüz çocuklar!"
    )

    audio_path = output_dir / "mandalina_ses.mp3"
    print("🎙️ 1/3: Ses üretiliyor...")
    try:
        openai.synthesize_speech_to_mp3(text=narration_text, output_path=audio_path)
        print(f"✅ Ses hazır: {audio_path}")
    except Exception as e:
        print(f"❌ Ses hatası: {e}")
        return

    # Zaten indirilmişse tekrar Kling'e istek atma
    video_path = output_dir / "mandalina_background.mp4"
    if not video_path.exists():
        kling_prompt = (
            "A cute anthropomorphic mandarin orange character for preschool children. "
            "Small arms, small legs, big shiny eyes, smiling face. Soft, colorful, friendly. "
            "3D cartoon Pixar style. Standing in a colorful kindergarten classroom. "
            "Bright lighting, cheerful atmosphere, vibrant colors. "
            "Character is animated, slightly bouncing and moving happily. "
            "Very cute, kid-friendly, educational style. Vertical video, no text on screen."
        )
        print("🎬 2/3: Kling videosu üretiliyor...")
        try:
            task_id = kling.create_task_with_custom_prompt(kling_prompt)
            video_url = kling.wait_for_video_url(task_id)
            kling.download_video(video_url, video_path)
            print(f"✅ Video indirildi: {video_path}")
        except Exception as e:
            print(f"❌ Kling hatası: {e}")
            return
    else:
        print("✅ 2/3: Video zaten var, atlanıyor.")

    final_output = output_dir / "MANDALINA_FINAL.mp4"
    print("✂️ 3/3: Birleştiriliyor...")

    VideoFileClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips = _load_moviepy()
    try:
        video_clip = VideoFileClip(str(video_path))
        audio_clip = AudioFileClip(str(audio_path))

        video_duration = float(video_clip.duration)
        audio_duration = float(audio_clip.duration)

        # Videoyu ses uzunluğuna kadar kopyalayıp birleştir
        loops = int(audio_duration / video_duration) + 1
        looped_video = concatenate_videoclips([video_clip] * loops)

        try:
            looped_video = looped_video.subclipped(0, audio_duration)
            final_video = looped_video.with_audio(audio_clip)
        except AttributeError:
            looped_video = looped_video.subclip(0, audio_duration)
            final_video = looped_video.set_audio(audio_clip)

        final_video.write_videofile(
            str(final_output),
            codec="libx264",
            audio_codec="aac",
            fps=video_clip.fps or 30,
            threads=4,
            logger=None
        )
        print(f"\n✅ Hazır: {final_output}")
    except Exception as e:
        print(f"❌ Birleştirme hatası: {e}")

if __name__ == "__main__":
    main()