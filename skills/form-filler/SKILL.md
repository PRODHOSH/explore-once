---
name: form-filler
description: Fill web forms for the person, built for developers filling recruitment, internship, hackathon, club and scholarship forms. Keeps a local profile of their real projects, experience, clubs and links, drafts open-ended answers (describe a project, why hire you, challenges, strengths) in their own voice using only facts they gave, lints the text for AI tells and invented numbers, fills the form in one scripted pass, then stops for review. Submitting needs an approval code tied to the exact page and data. Use this skill whenever the user wants Claude to fill in, complete, apply to or register on any web form, answer "why should we hire you" or "tell us about a project" style questions, reuse their details across applications, or says "fill this out for me", even if they do not mention scripts.
license: Apache-2.0
compatibility: Python 3.9+, Google Chrome, and `pip install playwright`.
---

# Form filler

Filling forms click by click costs a page read per field, and open-ended questions are where generic, invented-sounding answers creep in. This skill splits the work: a **profile** holds the person's true facts, a **script** fills the form in one pass, a **linter** blocks machine-sounding or untrue text, and a **review gate** makes sure a human approves before anything is sent.

## Setup (once)
1. `python3 -m pip install playwright`
2. Sign in to the sites you need: `python3 scripts/flowkit.py start <form url>` (sessions persist in the automation Chrome profile).
3. Create the profile: `python3 scripts/profile.py init`. It lives in `~/.explore-once/profile/` (owner-only, never committed or sent anywhere). Fill it by asking the person, not by guessing. See "Building the profile".

## Workflow

1. **Read the form.** `python3 scripts/fill_form.py --url "<url>" --list-fields` prints every question with its type, required flag, options and character limit.
2. **Load what you know.** `python3 scripts/profile.py facts` for the digest, `profile.py missing` for common gaps, `profile.py find-answers "<topic>"` for answers the person already approved before.
3. **Ask for what is missing, in one batch.** Anything the form needs that the profile lacks (a metric, notice period, expected pay, a reason for choosing this company): ask the person plainly, then **save the answer** with `profile.py set <path> <value>` or `profile.py add projects '{...}'` so they are never asked twice. Never fill a gap with a plausible guess.
4. **Draft the answers.** Short fields come straight from the profile. Open-ended ones: read `references/writing-answers.md` and write them in the person's voice. Then lint each one: `python3 scripts/lint_answer.py --text "..." --max-chars <limit>`. Fix every problem and re-lint until clean.
5. **Build `data.json`** as `{"question text": value}` using the form's own wording. For files use a path (resume), for checkboxes `true` or `false`.
6. **Review phase (submits nothing):**
   `python3 scripts/fill_form.py --url "<url>" --data data.json --out ./form-out`
   Read the JSON and open `form-out/review.png`. Check `unmatched_keys`, `required_not_provided`, `answer_lint`, `sensitive_fields_for_you`.
7. **Show the person**: the filled values, the full text of each open-ended answer, anything left for them, and the screenshot. Ask for their go-ahead. If they edit an answer, go back to step 4 for that answer and review again.
8. **Remember approved answers:** `profile.py save-answer --tags why-hire --q "<question>" --a "<answer>"` so the next form reuses the same true story.
9. **Submit only after they say yes:**
   `python3 scripts/fill_form.py --url "<url>" --data data.json --out ./form-out --submit <approval_code>`
   The code is a hash of the URL and the data, so a stale code is refused (exit 2). Submit is also blocked (exit 3) while the answers fail the lint, a required field is missing, or a field errored. Report what the confirmation page actually showed. Do not say it worked unless the page says so.

## Building the profile
Ask in small groups and write as you go (`profile.py set` / `add`):
- **Basics and links:** full name, email, phone, location, GitHub, LinkedIn, portfolio, resume file path.
- **Education:** school, degree, field, dates, grade if they want it shown.
- **Projects (the important part):** for each one: name, one line, the problem it solves, what they built, the stack, their role, what is live or shipped, links, and the **hardest thing** they dealt with. Metrics only if the person states them, with where the number comes from (`metrics[].source`).
- **Experience, clubs and activities, achievements:** role, what they actually did.
- **Availability:** notice period, start date, work authorization, relocation, roles they want.
- **About:** strengths and weaknesses with real examples, career goal, why they want this kind of work.
- **Voice:** one paragraph they wrote themselves, saved in `voice.samples`.
Profile fields are described in `assets/profile.template.json`.

## Rules that do not bend
- **True facts only.** Every claim in an answer traces to the profile or something the person said in this chat. Unknown means ask.
- **Human gate before submit.** Nothing is sent without the approval code from a review the person saw.
- **Sensitive fields are theirs.** The script refuses passwords, cards, CVV, SSN and bank fields and lists them. Voluntary diversity questions, expected salary, work authorization and consent boxes ("I certify...") are the person's decisions: use their stored answers or ask. Do not infer.
- **No CAPTCHAs, no login bypass.** Exit 4: the person handles it in the automation Chrome window.
- **Privacy.** The profile is personal data. Keep it local, never paste it into issues or commits, and never share it with outside services.
- Single-page forms only. For multi-step wizards, review each step before the "Next" that commits data.

## Many forms
Loop yourself, one review per form. Never batch-submit. Show a compact table of results and let the person approve each, or approve a batch explicitly ("submit all 5 as reviewed").

## When matching goes wrong
Keys match fields by label, placeholder, aria-label and name, fuzzily and one to one. If a key lands wrong or nowhere, use the exact wording from `--list-fields`. For an odd submit button pass `--submit-selector`. For custom widgets (date pickers, autocomplete) that are not real inputs, fill the rest with the script and finish that field with the browser tool.

## Exit codes
0 ok | 2 setup, bad JSON, or approval code mismatch | 3 step failed, form not fully fillable, or answers failed the lint (read the lists in the JSON) | 4 needs a human (login or challenge).
