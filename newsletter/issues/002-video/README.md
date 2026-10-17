# Nordic Crypto issue #2 — newsreel (site cut)

Source tooling for newsletter issue #2. Newsreel cut only.

The live site uses this cut. `newsletter/published/issues.json` points at the
public release file. `video.mp4` itself stays gitignored; `build.py` downloads it.

Voice: edge-tts `en-GB-ThomasNeural` at `+12%`. `tts.py` sends that voice to
`api.msedgeservices.com`, the host Edge 155 uses. `speech.platform.bing.com` answers
the synthesis socket with 403. Straight male newsreader in the manner of
NRK's Gislefoss: calm, clear, no jokes. Lead and tail pauses are shorter than the
`+2%` issue #1 cut, so the faster read does not leave a gap between pictures.

Brand on screen and in the voice: **Nordic Crypto**.
Sign-off: **The Nordic Crypto team**.
Title card: **Nordic Crypto #2**.
Kaupr is named only on the Ace Digital story card, as its source.
The Socialist Left card is labelled **Proposal**.
The narration does not say the programme is made with artificial intelligence.

Look: the media kit at nordiccrypto.no/media. The key shield is drawn from `assets/brand/shield-band.svg`;
wordmark "Nordic" in Sailcloth and "Crypto" in Shield Gold, Cormorant Garamond Bold; text in Schibsted Grotesk;
North Sea, Shield Gold, Sailcloth, Pine Tar and Sea Foam. The published #2 cut predates this and used the old crest.

## Rebuild the site cut

```bash
python3 -m pip install -r requirements.txt
python3 tts.py
python3 timeline.py
python3 audio.py --style news --timeline build/timeline.json --mix build/mix.wav
bash render_all.sh
bash concat.sh build/timeline.json build build/mix.wav build/nordic-crypto-2-newsreel.mp4
python3 render.py thumb
```

WAV mixes and MP4s are gitignored. The finished newsreel is a GitHub release asset
(`newsletter-002-newsreel-1`, file `nordic-crypto-2-newsreel.mp4`). `issues.json` stores
its sha256, byte size and duration.

Posters, from `thumbnail.png` (1280×720):

```bash
ffmpeg -i thumbnail.png -vf scale=320:180:flags=lanczos t.png && avifenc -q 60 t.png thumbnail-320.avif
ffmpeg -i thumbnail.png -vf scale=320:180:flags=lanczos -q:v 6 thumbnail-320.jpg
ffmpeg -i thumbnail.png -c:v libwebp -quality 78 thumbnail.webp
```
