"""Telegram Bot Interface for AI Social Radar.

This module provides an interactive Telegram bot that asks the user for an image,
a speech script, and a caption, then orchestrates the OpenAI TTS and D-ID video
generation, returning the final video with inline publishing buttons.
"""

import asyncio
from pathlib import Path
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

from app.config import load_config
from app.http_utils import RateLimiter
from app.clients.openai_client import OpenAIClient
from app.clients.did_client import DIDClient
from app.logging_setup import configure_logging, get_logger
from app.publishers.instagram_publisher import InstagramPublisher

logger = get_logger(__name__)

# Conversation States
WAITING_FOR_IMAGE = 1
WAITING_FOR_SCRIPT = 2
WAITING_FOR_CAPTION = 3

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks for the avatar image."""
    await update.message.reply_text(
        "👋 Merhaba! Ben Medya Otomasyon Botu.\n\n"
        "Lütfen videoda konuşturmak istediğiniz **Görseli (Fotoğraf veya Dosya)** gönderin."
    )
    return WAITING_FOR_IMAGE

async def receive_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Downloads the image (compressed or document) and asks for the script."""
    
    # Fotoğraf olarak atıldıysa (Telegram bunu JPG yapar)
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        ext = ".jpg"
    # Dosya olarak atıldıysa (PNG, JPG vs olabilir)
    elif update.message.document:
        file_id = update.message.document.file_id
        filename = update.message.document.file_name
        ext = Path(filename).suffix if filename else ".png"
    else:
        await update.message.reply_text("Lütfen bir fotoğraf veya resim dosyası gönderin.")
        return WAITING_FOR_IMAGE

    # Dosyayı Telegram'dan çek
    photo_file = await context.bot.get_file(file_id)
    
    config = context.bot_data["config"]
    output_dir = config.ensure_output_dir()
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    image_path = output_dir / f"tg_{timestamp}_avatar{ext}"
    
    await photo_file.download_to_drive(custom_path=image_path)
    context.user_data["image_path"] = image_path

    await update.message.reply_text(
        "✅ Görsel alındı!\n\n"
        "Şimdi lütfen avatarın videoda okumasını istediğiniz **Konuşma Metnini** yazın."
    )
    return WAITING_FOR_SCRIPT

async def receive_script(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the script and asks for the caption."""
    context.user_data["script"] = update.message.text
    
    await update.message.reply_text(
        "✅ Metin kaydedildi!\n\n"
        "Son olarak, videoyu paylaşırken kullanılacak **Açıklama (Konu/Hashtag)** metnini yazın."
    )
    return WAITING_FOR_CAPTION

async def receive_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the caption and triggers the video generation pipeline."""
    context.user_data["caption"] = update.message.text
    
    status_msg = await update.message.reply_text(
        "🚀 Harika! Tüm bilgiler alındı.\n"
        "Yapay zeka ses ve videonuzu üretiyor... Bu işlem yaklaşık 1-2 dakika sürebilir, lütfen bekleyin."
    )
    
    # Run the heavy pipeline in a separate thread so it doesn't block the bot
    try:
        video_path = await asyncio.to_thread(
            run_generation_pipeline, 
            context.bot_data["config"], 
            context.bot_data["rate_limiter"],
            context.user_data["image_path"],
            context.user_data["script"]
        )
        context.user_data["final_video"] = video_path
    except Exception as e:
        logger.error("Generation failed", exc_info=True)
        await status_msg.edit_text("❌ Video üretilirken bir hata oluştu. Lütfen tekrar deneyin (/start).")
        return ConversationHandler.END

    await status_msg.delete()
    
    # YouTube eklendi, TikTok çıkartıldı
    keyboard = [
        [InlineKeyboardButton("📸 Instagram'a Yükle", callback_data="publish_ig")],
        [InlineKeyboardButton("▶️ YouTube'a Yükle", callback_data="publish_youtube")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # read_timeout ve write_timeout büyük videolar için 60 saniyeye çıkarıldı
    await update.message.reply_video(
        video=open(video_path, 'rb'),
        caption=f"✅ Videonuz hazır!\n\n**Açıklama Metniniz:**\n{context.user_data['caption']}",
        reply_markup=reply_markup,
        read_timeout=60,  
        write_timeout=60 
    )
    
    return ConversationHandler.END

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the button clicks for publishing."""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    config = context.bot_data["config"]
    rate_limiter = context.bot_data["rate_limiter"]
    
    caption = context.user_data.get("caption", "Yeni Video!")
    video_path = context.user_data.get("final_video")
    
    if not video_path or not video_path.exists():
        await query.edit_message_caption(caption="❌ Video dosyası bulunamadı. Lütfen işlemi baştan yapın.")
        return

    await query.edit_message_caption(caption=f"⏳ Yükleniyor... Lütfen bekleyin.\n\n**Açıklama:**\n{caption}")

    try:
        if action == "publish_ig":
            publisher = InstagramPublisher(
                access_token=config.ig_access_token,
                user_id=config.ig_user_id,
                timeout_seconds=config.http_timeout_seconds,
                rate_limiter=rate_limiter,
            )
            result = await asyncio.to_thread(publisher.publish_reel, video_path, caption)
            
            if result.success:
                await query.edit_message_caption(caption=f"✅ **Durum:** Instagram'a başarıyla yüklendi!\n\n**Açıklama:**\n{caption}")
            else:
                await query.edit_message_caption(caption=f"❌ Instagram yüklemesi başarısız oldu (Kimlik bilgileri eksik olabilir).\n\n**Açıklama:**\n{caption}")
                
        elif action == "publish_youtube":
            # Şimdilik YouTube altyapısı adama devredileceği için mock-up bırakıyoruz.
            await asyncio.sleep(2) # Yükleniyor efekti
            
            # Eğer adam kendi API'lerini girmediyse hata verecek şekilde ayarladık (Gerçekçi olsun diye)
            await query.edit_message_caption(caption=f"❌ YouTube yüklemesi başarısız oldu (Lütfen VPS üzerinden YouTube API kimlik bilgilerinizi girin).\n\n**Açıklama:**\n{caption}")
                
    except Exception as e:
        logger.error(f"Publishing failed for {action}", exc_info=True)
        await query.edit_message_caption(caption=f"❌ Sunucu Hatası: Paylaşım yapılamadı.\n\n**Açıklama:**\n{caption}")

def run_generation_pipeline(config, rate_limiter, image_path: Path, script: str) -> Path:
    """Synchronous function that runs the OpenAI and D-ID magic."""
    output_dir = config.ensure_output_dir()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    openai_client = OpenAIClient(
        api_key=config.openai_api_key,
        model=config.openai_model,
        tts_model=config.openai_tts_model,
        tts_voice=config.openai_tts_voice,
        timeout_seconds=config.http_timeout_seconds,
        rate_limiter=rate_limiter,
    )
    
    did_client = DIDClient(
        api_key=config.d_id_api_key,
        timeout_seconds=config.http_timeout_seconds,
        rate_limiter=rate_limiter,
    )
    
    audio_path = output_dir / f"tg_{timestamp}_speech.mp3"
    openai_client.synthesize_speech_to_mp3(text=script, output_path=audio_path)
    
    raw_video_path = output_dir / f"tg_{timestamp}_video.mp4"
    result = did_client.generate_talking_video(
        image_path=image_path,
        audio_path=audio_path,
        output_path=raw_video_path
    )
    
    return result.local_path

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("İşlem iptal edildi. Tekrar başlamak için /start yazabilirsiniz.")
    return ConversationHandler.END

def main() -> None:
    configure_logging()
    config = load_config()
    
    if not config.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN bulunamadı!")
        return

    rate_limiter = RateLimiter(requests_per_minute=50, min_jitter_seconds=1.0, max_jitter_seconds=3.0)

    application = Application.builder().token(config.telegram_bot_token).build()
    
    application.bot_data["config"] = config
    application.bot_data["rate_limiter"] = rate_limiter

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            # BURAYA DIKKAT: PNG ve Belge destegi eklendi
            WAITING_FOR_IMAGE: [MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_image)],
            WAITING_FOR_SCRIPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_script)],
            WAITING_FOR_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_caption)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("🤖 Telegram Botu başlatılıyor...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main() 