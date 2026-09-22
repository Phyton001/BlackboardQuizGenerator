# Blackboard question upload format

Source: Anthology help, "Upload or Import Questions" (Ultra) and "Upload Questions"
(Original course view), and Blackboard's sample file
`sample_upload_questions_original.txt`. Checked September 2026.

## File conventions

- Tab-delimited `.txt`. One question per line, first field is the type code.
- No header row. No blank lines between records; a blank line is processed as a record
  and returns an error. The sample file has no trailing newline.
- Blackboard's sample file is plain ASCII/UTF-8 with **no byte-order mark** and
  **CRLF** line endings. The script matches this by default (`--bom`, `--lf` override).
- `correct`, `incorrect`, `true`, `false` and other answer words must be in English.
- Recommended batch size: 250 records (Ultra page), 500 (Original page).
- Images are not supported. Duplicate questions are not detected. Uploaded questions
  take the default point value (zero unless set).
- A row with an error is skipped; the other rows still upload.

## Type codes

`TAB` marks a tab; `( )` groups repeat; `[ ]` is optional. U = accepted by Ultra
upload, O = accepted by Original course view upload.

| Code | U | O | Structure |
|---|---|---|---|
| `MC` | U | O | `MC TAB question TAB (answer TAB correct\|incorrect)` up to 100 answers |
| `MA` | U | O | `MA TAB question TAB (answer TAB correct\|incorrect)` up to 100 answers |
| `TF` | U | O | `TF TAB question TAB true\|false` |
| `ESS` | U | O | `ESS TAB question TAB [sample answer]` |
| `MAT` | U | O | `MAT TAB question TAB (answer TAB matching text)` one-to-one, up to 100 |
| `FIB` | U | O | `FIB TAB question TAB (answer)` up to 100 accepted answers |
| `FIB_PLUS` | U | O | `FIB_PLUS TAB question TAB variable1 TAB answer1 TAB answer2 TAB TAB variable2 TAB answer3` — groups separated by an empty field, up to 10 variables; blanks appear in the text as `[variable]` |
| `NUM` | U | O | `NUM TAB question TAB answer TAB [tolerance]` |
| `ORD` | – | O | `ORD TAB question TAB (answer)` in correct order, up to 100 |
| `SR` | – | O | `SR TAB question TAB sample answer` |
| `FIL` | – | O | `FIL TAB question` |
| `OP` | – | O | `OP TAB question` |
| `JUMBLED_SENTENCE` | – | O | `JUMBLED_SENTENCE TAB question TAB choice1 TAB variable1 TAB TAB choice2 TAB TAB choice3 TAB variable2` — each choice is followed by the variables it answers, then an empty field; a choice followed directly by an empty field is a distractor |
| `QUIZ_BOWL` | – | O | `QUIZ_BOWL TAB question TAB (question word) TAB TAB (answer phrase)` up to 103 interrogatives, 100 phrases |

The Ultra help page lists only the eight U types. The script therefore refuses the
Original-only codes under `--target ultra` (short answer is downgraded to `ESS` with
the sample, and reported).

## Lines from Blackboard's sample file

```
MC	Which ocean is the warmest?	Atlantic	correct	Pacific	incorrect	Arctic	incorrect
TF	Blaise Pascal was a 20th century sociologist ...	false
ESS	Give a few examples where you can help preserve marine ecosystems.	[Placeholder essay text]
MAT	Match the following animals to their native continent	Bullfrog	North America	Panda	Asia	Llama	South America
FIB	___ is the silicate mineral with the lowest melting temperature ...	Quartz
FIB_PLUS	"Four [a] and [b] years ago" is the beginning of the [c] delivered by [d].	a	score		b	seven		c	Gettysburg Address		d	Abraham Lincoln
NUM	Approximately, how many species of birds are there?	10,000	1000
```
