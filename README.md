# BlackboardQuizGenerator

This site accepts text-based questions and converts them into a downloadable format
suitable for importing into Blackboard as test questions.

This repository is a fork of
[OklahomaChristian/BlackboardQuizGenerator](https://github.com/OklahomaChristian/BlackboardQuizGenerator),
which is based on source code from [Algonquin College](https://www.algonquincollege.com)
and modified by [Oklahoma Christian University](https://www.oc.edu). The original
ASP.NET site and its `QuizParser` library are kept unchanged. A live installation of the
upstream site is at <https://ed.oc.edu/blackboardquizgenerator/Default.aspx>.

Released under the GNU GPL v3 (see `LICENSE`).

## What this fork adds: an offline converter and Claude Code skill

`skills/blackboard-quiz-generator/` re-implements the converter in Python (standard
library only) and packages it as a [Claude Code skill](https://docs.anthropic.com/en/docs/claude-code/skills),
so a test written in Word or plain text can be turned into a Blackboard question upload
file on your own machine, with no web service involved.

- Targets **Blackboard Ultra** by default; `--target original` for the Original course
  view.
- Covers all 14 question types in Blackboard's upload format (MC, MA, TF, ESS, MAT,
  FIB, FIB_PLUS, NUM, ORD, SR, FIL, OP, JUMBLED_SENTENCE, QUIZ_BOWL) and enforces
  which of them Ultra accepts.
- Reads `.docx` directly and restores Word's auto-numbering labels, which plain-text
  conversion loses.
- Validates every question and reports failures with line numbers before writing.
- Matches the conventions of Blackboard's own sample file (UTF-8 without BOM, CRLF,
  no trailing blank line).
- Fixes the original's matching-question export, which wrote `ERROR` into the file.

The full list of corrections and additions is in
[`skills/blackboard-quiz-generator/CHANGES.md`](skills/blackboard-quiz-generator/CHANGES.md).

### Install the skill

With the [`skills`](https://github.com/vercel-labs/skills) CLI:

```bash
npx skills add Phyton001/BlackboardQuizGenerator
```

Or clone the repo and symlink `skills/blackboard-quiz-generator` into `~/.claude/skills/`.
Then ask Claude to prepare a test for Blackboard; it reads the skill and runs the script.

### Use the converter on its own

```bash
python3 skills/blackboard-quiz-generator/scripts/bbquiz.py my_test.docx --check
python3 skills/blackboard-quiz-generator/scripts/bbquiz.py my_test.docx -o "Week 3 Quiz.txt"
```

Input format: [`reference/input-format.md`](skills/blackboard-quiz-generator/reference/input-format.md).
Upload steps: [`reference/ultra-upload-steps.md`](skills/blackboard-quiz-generator/reference/ultra-upload-steps.md).

Tests:

```bash
cd skills/blackboard-quiz-generator && python3 -m unittest discover -s tests -v
```

## The original site

The following question types are available in the ASP.NET site: multiple choice,
multiple answer, true/false, essay, fill in the blank, matching. It consists of `.aspx`
pages in C# and the `QuizParser` Visual Studio solution that handles parsing and output.
Pull requests and suggestions welcome.
