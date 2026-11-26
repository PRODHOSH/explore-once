# Security policy

These skills drive a real browser that may be signed in to your accounts, so security matters here.

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's private reporting instead: open the **Security** tab of this repository and choose **Report a vulnerability**.

Include what you found, how to reproduce it, and what you think the impact is. You will get an acknowledgement within a few days. This is a volunteer project, so fixes follow as quickly as the maintainer can manage, and you will be credited if you want to be.

## What counts

- A script that submits, posts, deletes or pays without the human approval step it promises.
- Leaking cookies, tokens, form data or screenshots to anywhere but the local machine.
- Opening the browser's debugging port beyond `127.0.0.1`.
- Path handling bugs that read or write files outside the folders the user chose.
- Anything that lets a web page steer the scripts into doing something the user did not ask for.

## Design choices you should know about

- Scripts use a **separate Chrome profile** at `~/.pro-skills/chrome-profile`, not your everyday one. Only sign in to accounts you are comfortable letting a local script act on.
- The debugging port binds to `127.0.0.1` only. Any program on your machine that can reach that port can control that Chrome, so treat it like a signed-in session left open.
- The scripts never type passwords, card numbers or one-time codes, and never try to solve CAPTCHAs.
- Form submission needs an approval code tied to the exact page and data.

## Supported versions

Only the latest release gets fixes.
