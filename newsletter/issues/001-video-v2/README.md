# Nordic Crypto issue #1 — newsreel v2 and sensational cut

Source tooling for newsletter issue #1.

The live site uses the **newsreel** cut. `newsletter/published/issues.json` points at the
public release file. `video.mp4` itself stays gitignored; `build.py` downloads it.

The sensational cut is a separate experiment. It is not the site video. Do not use its
space-kitten opening for Nordic Crypto.

## Next cut (not this site file)

jQrgen's next style is a calm male newsreader in the manner of NRK's Gislefoss: clear,
authoritative, deeper voice, unhurried public-broadcaster pacing. Not the sensational
house style.

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
