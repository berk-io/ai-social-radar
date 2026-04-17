# AI-Powered Social Media Language Tutor (Instagram Reels & TikTok)

This enterprise-grade automation pipeline generates daily English vocabulary lessons in a short vertical video format. It orchestrates OpenAI for content and voice synthesis, D-ID AI for highly realistic, lip-synced avatar generation, and MoviePy for automated text overlays and media compositing. The final assets are staged for seamless distribution to Instagram Reels and TikTok.

## Business Value 

- **Automated Content Generation:** Seamlessly orchestrates text, audio, and video synthesis into a single command workflow.
- **Brand Consistency:** Utilizes a fixed D-ID Presenter ID to maintain a recognizable, consistent AI mascot/avatar across all daily videos.
- **Robust Architecture:** Implements robust error handling, rate-limit management (throttling, jitter), and secure environment variable injection for enterprise reliability.
- **Scalable Distribution:** Modular publisher classes designed for Meta Graph API and TikTok Content Posting API integrations.

## Installation

### 1. Environment Setup

- Python 3.11+ is recommended.
- **Note on Text Rendering:** MoviePy requires **ImageMagick** for text overlays. Ensure ImageMagick is installed on your system and configured in MoviePy if you encounter text rendering issues on Windows.

Create and activate a virtual environment:

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Configuration (.env)

Create a `.env` file in the project root based on the provided variables.

- **OpenAI**
  - `OPENAI_API_KEY`: Your OpenAI API key.
  - `OPENAI_MODEL`: Chat model (e.g., `gpt-4o-mini`).
  - `OPENAI_TTS_MODEL`: Text-to-speech model (e.g., `tts-1`).
  - `OPENAI_TTS_VOICE`: Voice profile (e.g., `nova`).
- **D-ID AI**
  - `D_ID_API_KEY`: Your D-ID basic authentication key (`username:password`).
  - `D_ID_PRESENTER_ID`: The unique ID of your designed or uploaded avatar.
- **Social Media Integrations** (Requires appropriate API permissions)
  - `IG_ACCESS_TOKEN`, `IG_USER_ID`
  - `TIKTOK_ACCESS_TOKEN`, `TIKTOK_OPEN_ID`

## Execution

Run the daily pipeline:

```bash
python -m app.main
```

### Pipeline Architecture:

1. **OpenAI:** Generates a daily English word, its translation, and high-quality Text-to-Speech (`.mp3`).
2. **D-ID AI:** Submits the audio and `Presenter ID` to the D-ID Clips API, generating a perfectly lip-synced talking-head video.
3. **MoviePy:** Composites the media, adds the English word as a centered text overlay, and exports the final `.mp4`.
4. **Publishers:** Dispatches the final composite to configured social media endpoints.

## Output Management

All generated assets (audio track, raw avatar video, and final composite) are safely persisted in the `output/` directory with timestamped filenames for auditing and data integrity.

## Operational Notes

- The pipeline utilizes an internal `RateLimiter` with randomized jitter to prevent API throttling and ensure compliance with third-party rate limits.
- Designed to run autonomously via CRON jobs (Linux) or Task Scheduler (Windows).
