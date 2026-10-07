# Nordic Crypto logo concepts

Two original marks. Neither is wired into the site. The live header, favicon and newsletter logo stay as they are until one of these is chosen.

The name is **Nordic Crypto**. Wordmarks are left-aligned: icon, then the name.

Site colours used as context: ink `#111`, paper `#fff`, accent `#0f5ea8`, and the office-screen dark background `#0b0d10` with text `#f5f5f4`.

## A. Kalmar Union

A square banner in the colours of the Kalmar Union flag: a red Nordic cross on a yellow-gold field. The upright is set toward the hoist (more gold on the right than on the left).

The crypto touch is the joint of the cross. The arms meet in a square plate, and a small gold eye sits in that plate. At 16 px it still reads as a cross. Larger, the eye is a chain link.

A dark keyline keeps the gold field visible on white and on `#0b0d10`.

| | Light | Dark |
| --- | --- | --- |
| Field | `#F6C445` | same |
| Cross | `#C8102E` | same |
| Keyline | `#1A1206` | same |
| “Nordic” | `#111111` | `#F5F5F4` |
| “Crypto” | `#C8102E` | `#FF5C6C` |

`#C8102E` on white is strong enough for the word. On the near-black screen it is not, so the dark wordmark uses `#FF5C6C` (same red, lighter). The cross itself stays `#C8102E`: it sits on gold, and the cross is large.

## B. Heraldic

A shield and crown drawn for Nordic Crypto. It is not the Trondheim Blockchain Meetup logo and not the coat of arms of Trondheim.

Blue shield, gold Nordic cross (upright toward the hoist), a red square block where the arms cross, and a three-point gold crown. The block is the crypto charge: a single link you can still see at 16 px. The shield blue is in the same family as the site accent, a step deeper so the gold cross stays clear.

| | Light | Dark |
| --- | --- | --- |
| Shield | `#0C447C` | same |
| Cross and crown | `#F4C430` | same |
| Block | `#C8102E` | same |
| Keyline | `#1A1206` | same |
| “Nordic” | `#111111` | `#F5F5F4` |
| “Crypto” | `#0C447C` | `#F4C430` |

`#F4C430` is the cross colour. It is too close to white to use for the word on a light page, so on light the word uses the shield blue. On the dark screen the gold word is the one that reads.

## Files

- `kalmar/icon.svg`, `kalmar/wordmark.svg`, `kalmar/wordmark-dark.svg`
- `heraldic/icon.svg`, `heraldic/wordmark.svg`, `heraldic/wordmark-dark.svg`
- `previews/` — each icon rendered at 512, 32 and 16 px, then placed on white `#fff` and on the screen dark `#0b0d10`, plus the wordmarks and a front-page header mockup. `side-by-side.png` puts both concepts on one sheet.

The header mockups use the current site header (left-aligned, accent `#0f5ea8` on the buttons) with that concept’s mark in the brand. They are pictures for review, not a change to `build.py`.
