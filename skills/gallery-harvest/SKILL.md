---
name: gallery-harvest
description: Collect every image from an inspiration or gallery page (Dribbble, Behance, Pinterest-style grids, Awwwards, product listings, portfolios) with a Python script and give Claude a few numbered contact sheets instead of making it open and review each page or image one by one. Use this skill whenever the user shares a gallery, search-results or inspiration URL and wants Claude to review, compare, summarize or pull design ideas, trends, color palettes or patterns from many images, or says "go through all of these", "look at this whole page", "get me inspiration from", or "scrape the images", even if they do not ask for a script.
license: Apache-2.0
compatibility: Python 3.9+, Google Chrome, and `pip install playwright pillow`.
---

# Gallery harvest

Reviewing a gallery shot by shot costs a page visit and an image read per shot. This skill scrolls the page once, downloads the images, removes near-duplicates, and builds **contact sheets**: grids of 16 numbered thumbnails. Claude reads a handful of sheets (one image each) and opens full-size originals only for the numbers worth studying. For 80 designs that is about 5 images read instead of 80, plus 3-6 for the originals that matter.

## Setup (once)
`python3 -m pip install playwright pillow`, then `python3 scripts/flowkit.py start <url>` and sign in if the site requires it (sessions persist; see the browser-script-compiler skill for why a separate Chrome profile).

## Run
```bash
python3 scripts/harvest.py "<gallery url>" --out ./inspo/<topic> --max 80
```
One JSON line comes back: image count, sheet paths, skipped counts. Read the sheets in order (`sheet-01.jpg` ...). Numbers on the thumbnails match `index.json` (`n`, `file`, `link`, `title`, `w`, `h`) and `images/NNN.ext`.

Useful options: `--strip-query` (remove `?resize=` style parameters to fetch originals; try it when thumbnails come out small), `--next "a[rel=next]" --pages 3` (walk pagination), `--min-size` (drop small images), `--dedupe 0` (keep near-duplicates), `--max`.

## Reviewing well
1. **Skim all sheets first** and note recurring patterns (layout, color, type, density, illustration style) before judging anything.
2. **Pick 3-8 standouts by number** and open those originals (`images/NNN.ext`) to check detail the thumbnails hide: typography, spacing, microcopy.
3. **Answer the user's actual question**: a mood summary, a palette, a feature list, a ranked shortlist. Cite shots by number and link (`index.json`) so they can click through.
4. If the page needed login or returned few images, say so plainly rather than summarizing a partial set as if it were complete. Report how many images you actually saw.

## Exit codes
0 ok | 2 setup | 3 a step failed (JSON names the step; the bundle has a screenshot and accessibility tree. Typical fix: lower `--min-render`, raise `--scrolls`, or adjust `--next`) | 4 needs a human (login wall or challenge: ask the user to complete it in the automation Chrome window, then re-run).

## Use responsibly
- This is for personal reference and inspiration. The images belong to their creators: do not republish them, reuse them in a product, or present them as the user's work. Credit the source link when sharing.
- Respect each site's terms and robots rules; keep `--max` modest and do not hammer a site with repeated runs. If a site offers an API or export, prefer that.
- Never try to get around a login wall, paywall or bot challenge. Exit 4 and let the user act.
