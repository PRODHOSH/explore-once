---
name: form-filler
description: Fill out web forms (job applications, registrations, vendor or tax portals, surveys, support and booking forms) from a JSON file in one scripted pass, then stop and show a review screenshot so the person approves before anything is submitted. Submission needs an approval code tied to the exact page and data. Use this skill whenever the user wants Claude to fill in, complete, apply to, or register on one or many web forms, reuse the same details across forms, or says "fill this out for me" or "apply to these", even if they do not mention scripts, and always when the form would send something on their behalf.
---

# Form filler

Filling a form click by click costs a page read per field. This skill fills the whole form in one script run, then **stops**. A person looks at the result and decides. Submitting is a separate, deliberate step.

## Setup (once)
`python3 -m pip install playwright`, then `python3 scripts/flowkit.py start <form url>` and sign in if the form needs an account (sessions persist in the automation Chrome profile).

## Workflow

1. **Collect the data.** Build a JSON file of `{"field label": value}` from what the user gave you. Use the labels the form shows ("Full name", "Email address"). If the user's details are in several places, gather them first and ask only about what is missing or ambiguous. Do not invent values for required fields.
2. **Review phase** (default, submits nothing):
   ```bash
   python3 scripts/fill_form.py --url "<form url>" --data me.json --out ./form-out
   ```
   It prints one JSON line and writes `review.png` and `review.json`: what was filled, keys that matched no field, required fields you did not provide, fields it refuses to fill, and an `approval_code`.
3. **Show the person the result.** Open `review.png`, summarize the filled values, and call out every item in `unmatched_keys`, `required_not_provided` and `sensitive_fields_for_you`. Ask for their go-ahead. Their approval is for *this* review: if anything changes, run the review phase again.
4. **Submit only after they say yes:**
   ```bash
   python3 scripts/fill_form.py --url "<form url>" --data me.json --out ./form-out --submit <approval_code>
   ```
   The code is a hash of the URL and the data. A stale or wrong code is refused (exit 2), so the thing submitted is exactly what was approved. Check `after-submit.png` and the printed page text for a confirmation, and report what you actually saw. Do not say "submitted successfully" unless the page shows it.

## What it will not do
- It never fills password, card number, CVV, SSN or bank-routing fields. It lists them under `sensitive_fields_for_you`; the person types those themselves. Say so plainly.
- It does not solve CAPTCHAs or get around login walls (exit 4: ask the person to handle it in the automation Chrome window).
- It handles single-page forms. For multi-step wizards, run the review phase per step and confirm before each "Next" that commits data.
- Consent boxes ("I agree to the terms", "I certify that...") are the person's decision. Only tick them when the data file says so, and mention them in your summary.

## Many forms at once
Loop over a list of URLs or rows yourself, one review per form. Never batch-submit: the review step is the point. Show a compact table of results and let the person approve each, or approve a whole batch explicitly ("submit all 5 as reviewed").

## When matching goes wrong
Fields are matched to keys by label, placeholder, aria-label and name, fuzzily and one-to-one. If a key lands on the wrong field or none, make the key closer to the visible label, or read the page's accessibility tree and set `--submit-selector` for an odd submit button. For a custom widget (a date picker or autocomplete that is not a real input), fill the rest with this script and finish that one field with the browser tool.

## Exit codes
0 ok | 2 setup, bad JSON, or approval code mismatch | 3 a step failed, or the form was not fully fillable (read the `errors` and `required_not_provided` lists; bundle holds a screenshot) | 4 needs a human (login or challenge).
