import os
from pathlib import Path
from app.config import load_config
from app.clients.openai_client import OpenAIClient
from app.http_utils import RateLimiter

def generate_perfect_audio():
    config = load_config()
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    rate_limiter = RateLimiter(requests_per_minute=60, min_jitter_seconds=0.1, max_jitter_seconds=0.5)
    
    openai = OpenAIClient(
        api_key=config.openai_api_key,
        model=config.openai_model,
        tts_model=config.openai_tts_model,
        tts_voice=config.openai_tts_voice,
        timeout_seconds=config.http_timeout_seconds,
        rate_limiter=rate_limiter
    )
    
    # İŞTE KUSURSUZ METİN!
    # Başında English var. Arada es vermesi için bol boşluklu noktalar var.
    # Şiveyi düzeltsin diye "Türkçesi" dedik ve okunuşu (Pahn-go-lin) olarak verdik!
    narration_text = "English: Pangolin. . . . . Türkçesi: Pahn-go-lin."
    
    audio_path = output_dir / "pangolin_kusursuz_ses.mp3"
    
    print("🎙️ Kusursuz ses üretiliyor (Sıfır maliyet)...")
    try:
        openai.synthesize_speech_to_mp3(text=narration_text, output_path=audio_path)
        print(f"✅ Ses hazır: {audio_path}")
    except Exception as e:
        print(f"❌ Ses üretiminde hata: {e}")

if __name__ == "__main__":
    generate_perfect_audio()