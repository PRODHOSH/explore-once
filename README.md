<p align="center">
  <img src="docs/banner.png" alt="explore-once: Claude explores a site one time, Python replays it" width="100%">
</p>

<p align="center">
  <a href="https://github.com/PRODHOSH/explore-once/actions/workflows/ci.yml"><img src="https://github.com/PRODHOSH/explore-once/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Claude-Skills-D97757?logo=claude&logoColor=white" alt="Claude Skills">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="Apache 2.0"></a>
  <img src="https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen" alt="PRs welcome">
</p>

Browser skills for Claude that move repetitive work out of the model and into Python scripts.

> **Up to 98.7% fewer tokens on repeated work.** That is Anthropic's own measurement for moving work from step by step tool calls into code. On reviewing a gallery, explore-once cuts image tokens by about 84% (my estimate). [Numbers and sources](#token-savings)

## The problem

When Claude drives a browser, it re-reads the page on every click. Do the same task five times and you pay for the same page reads five times. Some jobs Claude cannot do at all on its own, like making an image, so it ends up clicking through ChatGPT or Gemini one screenshot at a time.

## What this does about it

Let Claude work out the task once. Save the working path as a short Python script. Run the script from then on, and call Claude back only when a website changes and one step breaks.

## The skills

| Skill | What it gives you |
|---|---|
| [`browser-script-compiler`](skills/browser-script-compiler) | The core loop: explore, compile, replay, repair. Keeps a library of your flows so the next session reuses them. Also works for browser tests. |
| [`web-image-generation`](skills/web-image-generation) | Claude cannot make images. Your signed-in ChatGPT or Gemini can. A script sends the prompt, waits, and saves the file. |
| [`gallery-harvest`](skills/gallery-harvest) | Point it at a Dribbble style page. It collects the images and gives Claude a few numbered contact sheets instead of 80 separate looks. |
| [`form-filler`](skills/form-filler) | Built for developers filling recruitment, internship and club forms. Remembers your real projects, writes answers in your voice, and never invents a number. Stops for your approval before anything is submitted. |
| [`ui-regression-suite`](skills/ui-regression-suite) | Checks every page at desktop and mobile size for errors, broken images, overflow and visual changes, and shows Claude only what failed. |

## Token savings

| What | Number | Where it comes from |
|---|---|---|
| Doing the work in code instead of step by step tool calls, one worked example | **150,000 to 2,000 tokens, 98.7% fewer** | [Anthropic engineering, Nov 2025](https://www.anthropic.com/engineering/code-execution-with-mcp) |
| Reviewing an 80 shot gallery with `gallery-harvest` | **about 84% fewer image tokens** (about 18k instead of 109k) | My estimate, method below |
| What a script run sends back to Claude | **17 and 32 tokens** in two sample runs | Measured in this repo's tests |
| Stagehand v4 against plain Playwright | "2x faster and 80% more token efficient" | [Browserbase](https://browserbase.com/blog/evolving-computer-use-with-code), vendor claim, no method given |
| One 7 step form flow through Playwright MCP | about 114,000 tokens | [Reported second hand](https://dev.to/leonting1010/playwright-mcp-burns-114k-tokens-for-one-workflow-heres-why-and-what-to-do-about-it-57k8), older version |

Read these with care:

- The 98.7% is one example in Anthropic's post (a Google Drive to Salesforce workflow), not a promise for every task. Your savings depend on how much page data a task would otherwise pull through Claude.
- The 114,000 figure is from an older Playwright MCP. A later [re-test](https://dev.to/aswani25/playwright-cli-vs-playwright-mcp-which-should-you-use-with-claude-code-1olh) found newer versions much closer to the CLI, so do not expect that gap today.
- The first run costs about what a normal run costs, because Claude still explores the site. The savings start from the second run.
- Gallery estimate: image tokens are about width x height / 750. Eighty separate 1280x800 screenshots come to about 109k. Five contact sheets plus five full size originals come to about 18k.
- Not yet benchmarked on live sites. Measure your own tasks.

Also checked: 53 automated tests pass on local test pages.

## Quick start

Install with the [skills.sh](https://www.skills.sh/) CLI (needs Node 22.20 or newer):

```bash
npx skills add PRODHOSH/explore-once
```

Want just one skill, for Claude Code?

```bash
npx skills add PRODHOSH/explore-once --skill form-filler -a claude-code
```

`--list` shows what is inside, and `-g` installs globally. Installs are counted anonymously, which is how repos show up on the skills.sh leaderboard.

Or install it as a Claude Code plugin:

```bash
/plugin marketplace add PRODHOSH/explore-once
/plugin install explore-once@explore-once
```

Then add the Python packages the scripts use:

```bash
python3 -m pip install playwright pillow
```

You can also copy any folder from `skills/` into `~/.claude/skills/`. Each skill stands alone.

The scripts use their own Chrome profile, because Chrome 136 and later ignore the debugging switch on your everyday profile. Open it once and sign in to the sites you use:

```bash
python3 skills/browser-script-compiler/scripts/flowkit.py start https://chatgpt.com
```

## Safe by design

- Anything that sends, submits or posts stops for your approval first. Form submission needs a code tied to the exact page and data you reviewed.
- Passwords, card details and CAPTCHAs are always left to you.
- Your profile and logins stay on your machine.
- Answers written for forms are checked for em dashes, stock phrases and numbers that are not in your profile.

## Status

The scripts and tests run against local test pages. The selectors for ChatGPT, Gemini and Dribbble have not been checked on the live sites yet, so the first real run may need a one line fix. Issues and pull requests for that are the most useful thing you can send. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Author

<a href="https://github.com/PRODHOSH"><img src="https://github.com/PRODHOSH.png?size=120" alt="PRODHOSH V.S" width="90" align="left" hspace="12"></a>

**PRODHOSH V.S**, building things people actually use.

[GitHub](https://github.com/PRODHOSH) · [Website](https://prodhosh.me) · [LinkedIn](https://www.linkedin.com/in/prodhoshvs)

<br clear="left">

## License

[Apache 2.0](LICENSE). If you reuse or build on this, keep the [NOTICE](NOTICE) file so the credit travels with it.

Not affiliated with Anthropic. Claude is a trademark of Anthropic.
