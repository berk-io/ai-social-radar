from pathlib import Path
from app.config import load_config
from app.clients.did_client import DIDClient
from app.http_utils import RateLimiter

def main():
    config = load_config()
    rate_limiter = RateLimiter(requests_per_minute=60, min_jitter_seconds=1.0, max_jitter_seconds=3.0)
    
    did_client = DIDClient(
        api_key=config.d_id_api_key,
        timeout_seconds=120.0,
        rate_limiter=rate_limiter,
    )

    print("🚀 27 saniyelik özel müşteri videosu üretiliyor, D-ID'ye bağlanılıyor...")
    
    # Kendi ses dosyanın adını buraya yazıyorsun (mandalina_ses.mp3 olduğunu varsaydım)
    result = did_client.generate_talking_video(
        image_path=Path("mandalina_avatar.jpg"),
        audio_path=Path("output/mandalina_ses.mp3"), 
        output_path=Path("output/musteri_teslimat_videosu.mp4")
    )
    
    print(f"✅ Video başarıyla hazırlandı! Dosya yolu: {result.local_path}")

if __name__ == "__main__":
    main()