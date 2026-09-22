# Changes from the original Blackboard Quiz Generator

This skill re-implements `QuizParser/QuizParser.cs`, `LegacyParser.cs`, `Question.cs`
and `StringUtils.cs` from this repository in Python, so it runs on a laptop without
the ASP.NET web service, and corrects the output for Blackboard Ultra. The original
code was written at Algonquin College and released under the GNU GPL v3 by Oklahoma
Christian University; the skill is GPL v3 too.

## Behaviour kept from the original

- Same input format: numbered questions, lettered answers, `*` for correct, `blank`
  and `match` keywords, and the older `MC`/`MA`/`TF`/`BL`/`ES` header blocks.
- Same paragraph splitting, orphan-answer rejoining, and Word smart-quote clean-up.

## Corrections for Blackboard

1. **Matching questions now export.** The original's text writer returned the literal
   word `ERROR` for every matching question and wrote it into the file. They are now
   written as `MAT` records, and a pair with an empty side (which Blackboard cannot
   grade) is reported instead of silently exported.
2. **Ultra type list enforced.** Ultra's upload accepts MC, MA, TF, ESS, FIB, FIB_PLUS,
   MAT and NUM only. Ordering, short answer, file response, opinion scale, jumbled
   sentence and quiz bowl questions are reported under the Ultra target, with the
   Original-target alternative named. Short answer is converted to an essay with its
   sample answer, and the conversion is noted in the report.
3. **File conventions match Blackboard's sample.** UTF-8 without a byte-order mark
   (the original always wrote one), Windows CRLF line endings, and no trailing blank
   line (Blackboard processes a blank line as a record and errors). Flags `--bom` and
   `--lf` restore the old behaviour if an installation needs it.
4. **Answer flags are lowercase English** (`correct`, `incorrect`, `true`, `false`) as
   in Blackboard's documentation; the original wrote `Correct` / `Incorrect`.
5. **Invalid questions never reach the file.** The script reports every failure with
   the input line number and the offending text and exits non-zero; `--allow-invalid`
   opts in to a partial file.
6. **Tabs and line breaks inside a field** are replaced with spaces in the library
   rather than only in the web page's text box, so `.docx` and stdin input are safe.
7. **Quoted fields unwrapped.** A field wrapped entirely in double quotes (a habit from
   CSV-based tools) is unwrapped; tab-delimited files do not need it.
8. **Legacy one-line blocks.** In the original, any single-line block was treated as a
   type header, so an essay under an `ES` header separated by a blank line could
   never parse. A one-line block that is not a header is now parsed with the active
   legacy type.
9. **Batch size warning** at 250 (Ultra) or 500 (Original) questions.

## Additions

- All 14 Blackboard upload types: `essay` (with sample), `blanks` (FIB_PLUS), `num`,
  `order`, `short`, `file`, `opinion`, `jumbled`, `quizbowl`, alongside the original's
  MC, MA, TF, essay, fill in the blank and matching. Each is built from Blackboard's
  published format table (see `reference/blackboard-format.md`).
- **Word input read directly.** `.docx` files are parsed paragraph by paragraph, with
  empty paragraphs kept as blank lines and Word's auto-numbering labels (`1.`, `a)`,
  `i.`) rebuilt from the document's numbering definitions. Plain-text export loses
  those labels, which is why the original tool asked users to paste into a text box.
  Older `.doc`, `.rtf` and `.odt` files are converted with macOS textutil or pandoc
  when available; saving as `.docx` in Word first is more reliable for `.doc`.
- `--check` validation mode, `--target ultra|original`, stdin input, a unit-test suite,
  and a SKILL.md so Claude can drive the whole conversion from a Word document.

## Not carried over

- The Blackboard **pool package** (zip of XML) download, which is Original-only and
  superseded by the question upload.
