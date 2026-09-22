---
name: blackboard-quiz-generator
description: Convert a test or quiz written in Word, Markdown, or plain text into a Blackboard question upload file (tab-delimited .txt for Blackboard Ultra or Original course view). Use whenever the user wants to upload, import, or convert quiz/test/exam questions for Blackboard (Ultra or Original) or an LMS "question upload" or "upload questions from file" feature; when they mention question pools, question banks, MC/MA/TF/essay/fill-in-the-blank/matching questions for an LMS; or when they paste exam questions and ask to get them into Blackboard. Runs entirely offline from a bundled Python script.
---

# Blackboard quiz generator

Turns a human-written test into the file that Blackboard's **Upload questions from file**
feature accepts. Works offline: one standard-library Python script, no web service.

Script: `scripts/bbquiz.py` (Python 3.9+). Default target is **Blackboard Ultra**.

## Workflow

1. **Get the source as text.** Plain `.txt` works directly, and so does `.docx`: the
   script reads Word files itself and restores auto-numbering labels. For an old `.doc`
   ask the user to save it as `.docx` (the macOS converter drops list labels). If the
   `--check` report shows the document is structured differently from the canonical
   format (a shared stem before several questions, answers in a table, an answer key
   at the end, unlabelled bulleted answers), read the document, rewrite the questions
   into the canonical input format below, and save that as a `.txt` next to the source.
   Never guess a correct answer: if the source has no answer key for a question, ask,
   or leave it out and say so.
2. **Validate:** `python3 scripts/bbquiz.py INPUT --check`
   The report lists each question as `[ ok ]` with its detected type or `[FAIL]` with
   the reason and the input line number. Fix the input (not the output) until every
   question is ok. Common fixes are in `reference/input-format.md`.
3. **Write the file.** Two output formats; ask which the user wants if unclear:
   - **Question bank package (preferred for Ultra):**
     `python3 scripts/bbquiz.py INPUT --format pool --points 0.5 --name "Bank name" -o "Bank name.zip"`
     A zip that Ultra's **Manage banks > + > Import > from file** accepts (the same package
     Original's Pools page exports). Points per question are stored in the package.
   - **Tab-delimited text:** `python3 scripts/bbquiz.py INPUT -o "Quiz Name.txt"`
     for a test's **Upload questions from file**. Add `--target original` for an Original
     course view.
   The script writes nothing if any question is invalid; use `--allow-invalid` only if
   the user explicitly wants a partial file.
4. **Hand over:** give the user the output path plus the upload steps in
   `reference/ultra-upload-steps.md`. For text uploads remind them that questions
   default to zero points; Blackboard skips (does not fix) any row it cannot read.

Always read the `--check` report before delivering, and tell the user the question
count and types that were written. Show the user any question the script rejected,
with the reason, rather than silently dropping it.

## Canonical input format (summary)

Questions are paragraphs separated by a blank line. See `reference/input-format.md`
for the full rules and every keyword.

```
1. Multiple choice question text?          <- number + . or )
a) wrong                                   <- letter + . or )
*b) right                                  <- asterisk marks correct; 2+ asterisks = multiple answer
c) wrong

2. A true/false statement.
True

3. An essay question has no answer lines.

blank 4. Fill in the ____ blank.           <- accepted answers, one per line
a. answer
b. alternative

blanks 5. Multiple [a] blanks [b] here.    <- variables in [brackets]; a. and b. lines give answers
a. first
b. second

match 6. Match these:
a. left / right

num 7. A numeric answer?
42 +/- 0.5
```

Also accepted: `essay N.` (optional sample answer on following lines), and for Original
course view only: `order N.`, `short N.`, `file N.`, `opinion N.`, `jumbled N.`,
`quizbowl N.`. The older `MC` / `MA` / `TF` / `BL` / `ES` header style from the
Algonquin tool still works.

## Blackboard Ultra rules the script enforces

- Ultra's upload accepts only MC, MA, TF, ESS, FIB, FIB_PLUS, MAT and NUM. Ordering,
  short answer, file response, opinion scale, jumbled sentence and quiz bowl are
  Original-only; under `--target ultra` the script reports them and stops (short answer
  is written as an essay with a sample answer instead, and says so).
- Matching pairs must be one-to-one; a pair with an empty side is rejected.
- No images or text-only blocks exist in the upload format: add them in the Ultra
  editor after upload.
- Text output conventions copied from Blackboard's own sample file: UTF-8 without BOM,
  Windows line endings, one question per line, no blank lines, no trailing blank line.
- Pool packages carry MC, MA, TF, essay, short answer, fill in the blank (single and
  multiple), matching, numeric, ordering and jumbled sentence. File response, opinion
  scale and quiz bowl exist only in the text format.
- Recommended batch size is 250 questions per file (500 for Original); the script warns.

## Reference files

- `reference/input-format.md`: every input keyword, with examples and fixes for common
  parse errors.
- `reference/blackboard-format.md`: the tab-delimited output spec for all 14 question
  types and which course view supports each.
- `reference/ultra-upload-steps.md`: click-by-click upload instructions for Ultra and
  Original.
- `examples/`: sample inputs covering every type; `tests/` has the unit tests
  (`python3 -m unittest discover -s tests`).

## Provenance and licence

Re-implementation in Python of the parsing rules of the Blackboard Quiz Generator,
written at Algonquin College and released under the GNU GPL v3 by Oklahoma Christian
University (https://github.com/OklahomaChristian/BlackboardQuizGenerator, live at
https://ed.oc.edu/blackboardquizgenerator/). This skill is GPL v3 as well. Changes for
Blackboard Ultra are listed in `CHANGES.md`.
