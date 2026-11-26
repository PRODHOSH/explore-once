# Contributing

Thanks for wanting to help. This project is a small set of Claude skills that move repetitive browser work out of the model and into Python scripts. Contributions that keep that idea sharp are very welcome.

## The fastest ways to help

- **Fix a broken selector.** Sites change their pages. If ChatGPT, Gemini or another site stops working, open a "Site changed" issue or send a pull request that updates `skills/web-image-generation/scripts/sites.json`. This is the most useful contribution you can make.
- **Report a bug** with the exit code and the JSON line the script printed.
- **Propose a skill.** Open a "Skill idea" issue first so we can agree on scope before you write code.
- **Improve the docs.** If something confused you, it will confuse the next person.

## Set up

You need Python 3.9 or newer and Google Chrome.

Fork the repository on GitHub and get your fork onto your machine with your usual Git workflow. Then, from the project folder, make a virtual environment and install the two packages the scripts use:

```bash
python3 -m venv .venv
```

```bash
.venv/bin/python -m pip install playwright pillow
```

## Before you open a pull request

Run these from the project folder. The first two need nothing but Python.

```bash
python3 tools/sync_shared.py
```

```bash
python3 tools/validate.py
```

```bash
.venv/bin/python tests/test_e2e.py
```

```bash
.venv/bin/python tests/test_more.py
```

The first one copies `shared/flowkit.py` into every skill. The second checks the skill rules, referenced files and drift. The last two run against local fake pages.

The tests use local fixture pages only. They never touch a real website or your real Chrome profile.

## Rules for skills

These keep every skill easy for Claude to load and easy for people to trust.

1. **One folder per skill** under `skills/`, with a `SKILL.md` whose `name` matches the folder name (lowercase, hyphens).
2. **The description says what the skill does and when to use it.** It is the only part Claude always sees, so put the trigger phrases there. Keep it under 1024 characters.
3. **Keep `SKILL.md` under 500 lines.** Move detail into `references/` and say when to read it.
4. **Skills are self-contained.** Users install one folder, so never import from outside it. Shared code lives in `shared/` and is copied in by `tools/sync_shared.py`. Edit the file in `shared/`, never the copies.
5. **Scripts print one short JSON line** and use the exit codes in `shared/flowkit.py` (0 ok, 2 setup, 3 step failed, 4 needs a human). Short output is the whole point: it saves tokens.
6. **Anything outward-facing needs a human gate.** Sending, submitting, posting, paying or deleting must stop for approval first. See `form-filler` for the pattern.
7. **Never automate credentials, CAPTCHAs or payment details.** Scripts exit with code 4 and let the person act.
8. **Be honest about what is tested.** If you could not check something against a live site, say so in the skill and the pull request.
9. **Add or update a test** for new script behavior, using a local fixture page.

## Commit messages

Short and plain, in the imperative: `Add form-filler skill`, `Fix radio group matching`. One idea per commit.

## Pull requests

Use the template. Keep pull requests focused, link the issue, and describe how you tested. A maintainer will review as soon as they can.

## License

By contributing you agree that your work is licensed under the Apache License 2.0, the same as the rest of the project. Please keep the copyright and NOTICE files intact.
