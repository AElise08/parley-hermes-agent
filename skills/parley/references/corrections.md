# Corrections

The rule that makes a chat tutor usable on a phone: partner first, corrections
second, and never more than three on screen.

## Shape

1. Reply to the content of what they said, in the target language, at their
   level. One to three short sentences plus one follow-up question.
2. Then up to three corrections, in their native language:

   ✏️ "Yesterday I go" → "Yesterday I went" — passado de go é went.

   Each is: what they wrote, the better version, one line of why.
3. Log every correction — shown or not — with `tutor.py error add`.

## What to correct

- At A1–A2: only what blocks meaning. Word order, missing verb, wrong tense
  that changes when something happened. Let articles and prepositions ride.
- At B1–B2: tense, agreement, word choice, false friends (PT→EN classics:
  "pretend" ≠ pretender, "actually" ≠ atualmente, "push" ≠ puxe).
- At C1–C2: register and idiom. "Moreover" in a text message, "a lot" in an
  essay. Say what a native would actually write.

## What not to do

- No walls of correction. More than three and the conversation dies.
- No correcting their native language when the pair points the other way.
- No invented mistakes. If a turn was clean, say so in four words and move on.
- Repeated mistake, same entry: `error add` merges on the same (wrong, better)
  pair, resets its schedule, and bumps the count. You do not need to manage
  duplicates.
