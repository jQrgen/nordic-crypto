# Nordic Crypto issue #1 — newsreel v2 and sensational cut

Source tooling for the issue #1 newsreel (and optional sensational cut).
The finished newsreel replaces `newsletter/published/001/video.mp4` on publish.
Kaupr is a **news source** and may sponsor **events**; it is **not** a sponsor of Nordic Crypto or the newsletter — do not add a midroll or “brought to you by” for Kaupr.

Brand on screen and in the voice: **Nordic Crypto**.
Sign-off: **The Nordic Crypto team**.
Jørgen's name is spoken and shown only in the 28 October Nexa / Bitcoin Unlimited disclosure.

Facts in the narration come from issue #1. The voice is edge-tts `en-GB-RyanNeural` at `+20%`
(an energetic anchor pace; the earlier pass was `+6%`). Lead and tail pauses are short so
sections do not sit in silence.

## Two cuts

| Cut | Look | Opening |
| --- | --- | --- |
| Newsreel | Classic lower-thirds, ticker, section wipes | 5.5s original brass jingle |
| Sensational | Hyperspace streaks, flashes, kinetic wipes, space-kitten cameos | 8s original super jingle |

The sensational jingle, stingers and bed are synthesized in `audio.py` (numpy). They are not
taken from any film or broadcast theme. The kittens are drawn in code.

## Rebuild

```bash
python3 -m pip install -r requirements.txt
python3 tts.py          # only if the spoken script changes; needs network
python3 timeline.py
python3 timeline.py --bumper 8 --section 1.65 \
  --timeline build/timeline_flash.json --subs subs_flash.srt --script script_flash.txt
python3 audio.py --style news  --timeline build/timeline.json       --mix build/mix.wav
python3 audio.py --style flash --timeline build/timeline_flash.json --mix build/mix_flash.wav
bash render_all.sh       # sequential, one segment at a time
bash render_flash_all.sh
bash concat.sh build/timeline.json build build/mix.wav build/nordic-crypto-1-newsreel.mp4
bash concat.sh build/timeline_flash.json build/flash build/mix_flash.wav build/nordic-crypto-1-sensational.mp4
```

WAV mixes and MP4s are gitignored. Finished files for review are delivered as artifacts,
not committed.
