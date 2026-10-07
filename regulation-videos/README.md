# Regulation explainer videos

Five short Nordic Crypto explainers — Norway, Sweden, Denmark, Finland and Iceland — on how crypto rules are decided and enforced. The public page is `/regulation-videos/`, built by `tools/regulation_videos.py` from `data/regulation-videos.json` and the editor-approved `rules.json`.

| Path | What it is |
|---|---|
| `scripts/` | Narration for each country (English). The page shows these lines as narrator notes. |
| `storyboards/` | Shot lists in the newsreel layout (left-weighted; never centered). |
| `sources/SOURCES.md` | Source list taken from `rules.json`. The page links the same URLs. |
| `posters/` | Still frames used as the HTML5 poster. They are not the film. |
| `media/` | Drop `video-XX.mp4` and `subs-XX.vtt` here. MP4s are gitignored. |
| `substack/` | Draft notes for later human review. The build does not send them. |
| `pipeline/README.md` | How a later render can reuse the newsletter newsreel. |

The films are not rendered yet. Each slot plays an MP4 from this site when the file is present. Until then the slot shows the title, the narrator notes and the sources.

Brand on the page and in the scripts: Nordic Crypto. Sign-off: The Nordic Crypto team. Kaupr is not a sponsor of these films. The openers do not say the films were made with artificial intelligence.

Iceland is in the EEA, not the EU. Seðlabanki Íslands houses Fjármálaeftirlit.
