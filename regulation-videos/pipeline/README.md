# Video pipeline notes

Existing newsreel pipeline: `newsletter/issues/001-video-v2/` (PIL frames → ffmpeg, edge-tts ThomasNeural +2%).

## Reuse
- Voice, brand bug, lower-thirds, ticker, audio jingle (`audio.py --style news`).
- Do **not** copy sensational/flash cut.
- Adapt `content.py` VO/TIMELINE per country from `scripts/*-script.txt`.

## Render status
| Country | Scripts | Storyboard | TTS/MP4 |
|---------|---------|------------|---------|
| NO | ready | ready | not rendered |
| SE | ready | ready | not rendered |
| DK | ready | ready | not rendered |
| FI | ready | ready | not rendered |
| IS | ready | ready | not rendered |

Full five-country render is heavy on the box; site wiring + scripts first per product goal.
