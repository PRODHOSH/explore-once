# Writing answers that sound like the person

Recruitment forms are read by people who have read hundreds of them. Generic answers get skipped. Specific, true, plainly written answers get remembered. Your job is to sell the person's real work in their own voice, using only facts they have given you.

## The hard rules

1. **Facts come from the profile or from the person, nothing else.** Run `profile.py facts` before drafting. If you need a fact that is not there (a metric, a user count, a team size, a company detail), ask. Never estimate, round up, or "make it plausible".
2. **No numbers unless they are in the profile.** The linter enforces this. A project with no stated numbers is still a good project: describe what it does and what was hard.
3. **No em dashes or en dashes, no exclamation marks, no emoji, no markdown or bullets** in text boxes. Use commas and full stops.
4. **No stock phrases.** Banned list lives in `scripts/lint_answer.py` (passionate, leverage, seamless, robust, "I am excited to", "proven track record", "team player", and so on). If a sentence could appear in anyone's application, rewrite it with a detail only this person has.
5. **Do not claim traits, show them.** Not "I am a quick learner", but "I had not used WebSockets before, so I built the chat feature first to learn them".
6. **Never overstate.** If the project was a college build with a handful of testers, say that. Honest scale reads as confidence.

## Voice

Read `voice.samples` and `voice.notes` in the profile and mirror them: sentence length, how casual, which words they actually use. If there are no samples, ask the person for one short paragraph they wrote themselves (a message, a README intro) and save it with `profile.py add voice.samples '"<their paragraph>"'`. Defaults when you have nothing: first person, plain words, contractions are fine, short and medium sentences mixed naturally, casual but professional, like a good message to a colleague you respect.

## Shape of a good answer

- **Describe a project:** the problem (one sentence), what you built and how it works (two or three sentences, name the stack once), the hardest part and what you decided, where it stands now (live, repo link if the form wants one). Link or repo names only from the profile.
- **Why should we hire you:** pick one or two real projects or experiences that match what this role asks for. Say what you did and what it shows. Close with a plain statement about what you want to work on there. Match to the role using the job text on the page or what the person told you, not guesses about the company.
- **Why this company / role:** use only what the person told you or what is written on the page you can see. If you have nothing specific, ask for one honest reason. A vague reason is worse than a short true one.
- **Challenge you overcame:** one real situation from a project. What broke, what you tried, what worked, what you would do differently.
- **Clubs and activities:** list them with the role and one concrete thing done in each. Counts only if the profile has them.
- **Strengths / weaknesses:** tie each to a real example. For a weakness, name something real and what the person is doing about it (from `weaknesses_and_growth`).
- **Where do you see yourself / goals:** use `career_goal`. Keep it modest and specific.
- **Availability, notice period, relocation:** copy from `availability` exactly.
- **Expected salary:** never guess. Ask every time, or use what the person said for this specific form.
- **Voluntary diversity or demographic questions:** never infer. Answer only from what the person has told you, otherwise leave it for them (or choose "prefer not to say" only if they said to).

## Length

Respect `maxlength`. Aim for 70 to 90 percent of the limit, never above it. With no limit: 3 to 5 sentences for short questions, 100 to 180 words for "describe a project" or "why us". Long is not better.

## Check, then show, then remember

1. Draft, then run `lint_answer.py --text "..." --max-chars N`. Fix every problem it lists. Add `--allow "<company name>"` or a year only when it is printed on the form.
2. Show the person the final text before filling. They approve or edit.
3. After they approve, save it: `profile.py save-answer --tags why-hire --q "<question>" --a "<answer>"`. Next time `find-answers` gives you their approved wording to adapt, so every form tells the same true story.
4. Anything new you learned while asking questions goes into the profile with `set` or `add`, so the person never has to answer the same question twice.

## Illustrative before and after

These use made-up facts to show tone only. Never reuse them.

Before (reads as machine-made):
> I am passionate about leveraging cutting-edge technologies to build robust, scalable solutions. My proven track record makes me a perfect fit for your dynamic team!

After (specific and plain, from a made-up profile):
> Last year my hostel kept losing track of mess attendance, so I built a small web app where students tap in and the warden gets a daily sheet. The hard part was people on slow phones, so I made the page work without JavaScript frameworks and it loaded fine on the worst connection I could find. I would like to keep building tools like that, where a real group of people uses the thing every day.

Notice what changed: a real problem, what was built, one hard detail, no adjectives about the writer, no numbers that were not given.
