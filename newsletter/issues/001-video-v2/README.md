# Nordic Crypto issue #1 — newsreel (site cut)

Source tooling for newsletter issue #1.

The live site uses the **newsreel** cut. `newsletter/published/issues.json` points at the
public release file. `video.mp4` itself stays gitignored; `build.py` downloads it.

Voice: edge-tts `en-GB-ThomasNeural` at `+2%`. Straight male newsreader in the manner of
NRK's Gislefoss: calm, clear, no jokes. This replaces `en-GB-RyanNeural` at `+20%`.
Lead and tail pauses are a little longer than that faster cut.

Brand on screen and in the voice: **Nordic Crypto**.
Sign-off: **The Nordic Crypto team**.
Jørgen's name is spoken and shown only in the 28 October Nexa / Bitcoin Unlimited disclosure.
Kaupr is spoken and shown only as the source of the GreenMerc / Northcrypto story.
The narration does not say the programme is made with artificial intelligence, and it does
not say Kaupr sponsors the meetup, the newsletter, or Nordic Crypto.

The sensational cut is a separate experiment. It is not the site video. Do not publish it.

## Two cuts

| Cut | Look | Opening | Publish |
| --- | --- | --- | --- |
| Newsreel | Classic lower-thirds, ticker, section wipes | 5.5s original brass jingle | Yes — this is the site file |
| Sensational | Hyperspace streaks, flashes, kinetic wipes, space-kitten cameos | 8s original super jingle | No |

The sensational jingle, stingers and bed are synthesized in `audio.py` (numpy). They are not
taken from any film or broadcast theme. The kittens are drawn in code.

## Rebuild the site cut

```bash
python3 -m pip install -r requirements.txt
python3 tts.py
python3 timeline.py
python3 audio.py --style news --timeline build/timeline.json --mix build/mix.wav
bash render_all.sh
bash concat.sh build/timeline.json build build/mix.wav build/nordic-crypto-1-newsreel.mp4
```

WAV mixes and MP4s are gitignored. The finished newsreel is a GitHub release asset
(`newsletter-001-newsreel-3`, file `nordic-crypto-1-newsreel.mp4`). `issues.json` stores
its sha256, byte size and duration. Do not upload the sensational file.
