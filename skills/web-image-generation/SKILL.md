---
name: web-image-generation
description: Generate images by driving the user's already-logged-in ChatGPT or Gemini in Chrome with a Python script - sends the prompt, waits for the picture, downloads the file - so Claude (which cannot generate images itself) gets images without spending tokens on screenshots and clicking. Use this skill whenever the user asks Claude to make, draw, create or generate an image, logo, illustration, mockup, icon, hero image, thumbnail or concept art, wants several variations, or says to use ChatGPT, Gemini, DALL-E or Nano Banana for images, even if they do not mention scripts or the browser.
---

# Web image generation

Claude cannot produce images, but the user usually has ChatGPT and/or Gemini signed in. A script can do the whole round trip (open site, send prompt, wait, save file) while Claude spends tokens only on writing a good prompt and checking the result.

## Before the first run (once)

1. `python3 -m pip install playwright`
2. `python3 scripts/flowkit.py start https://chatgpt.com` and sign in to ChatGPT and/or Gemini in that window. The session persists. (Why a separate Chrome profile: see `references/troubleshooting.md`.)

## Generate

```bash
python3 scripts/generate_image.py --site chatgpt --prompt "<prompt>" --out ./images
python3 scripts/generate_image.py --site gemini  --prompt-file prompt.txt --count 2
```

It prints one JSON line with the saved file paths. Then **look at the image** before telling the user it is done: check it matches the brief, text is spelled correctly, and nothing is cropped. If not, refine the prompt and run again; say what you changed.

Pick the site by the user's preference; if they have no preference, use the one that is logged in (`--inspect` shows quickly). ChatGPT tends to follow long, detailed prompts and render text well; Gemini is a good second opinion. Do not promise one over the other without testing on the user's task.

## Writing the prompt (this is where Claude adds value)

Image models reward specificity. Cover: subject, style or medium, composition and camera or framing, lighting, color palette, aspect ratio, and any text to appear verbatim (in quotes). State exclusions positively ("clean empty background") because negations are unreliable. For several variations, change one dimension at a time so the user can compare.

## Exit codes
| Code | Meaning | You do |
|---|---|---|
| 0 | image(s) saved | inspect the file, report the path |
| 2 | setup problem | follow the message (install, Chrome missing) |
| 3 | a step failed | read the bundle (below) |
| 4 | needs a human | not logged in or a challenge appeared: ask the user to sign in in the automation Chrome window, then re-run |

On exit 3 the JSON names the step and a `bundle` folder. `aria.txt` often shows the model's reply, which explains most failures: a content-policy refusal (adjust the prompt; do not try to evade the policy), a usage limit (tell the user, stop), or a UI change. For a UI change run `generate_image.py --site X --inspect`, fix the ordered selector lists in `scripts/sites.json` (input box, send button, stop button), and re-run. Update the `verified` note there once it works. This repair costs a few thousand tokens, once, instead of every run.

## Honest limits
- The selectors in `sites.json` shipped **unverified against the live sites**; expect to run `--inspect` and adjust on the first use. Image detection itself is site-agnostic (new large `<img>` that stops changing).
- Free plans have daily image limits and may downscale or watermark; report what happened rather than retrying in a loop.
- Automating a consumer chat UI may be against that provider's terms and can trigger bot checks. It is meant for the user's own account at human-like volume, one request at a time. If the user needs volume, point them to the official image APIs.
- Never attempt to solve a CAPTCHA; exit 4 and let the user handle it.
- Respect copyright and policy: no images of real people in misleading contexts, and no passing off generated images as photographs.
