# Input format

The converter reads plain text. Each question is a paragraph; paragraphs are separated
by one or more blank lines. Lines are trimmed, tabs become spaces, and Word's curly
quotes and non-breaking spaces are normalised, so pasting from Word is fine.

Word `.docx` files are read directly: each paragraph becomes a line, empty paragraphs
become blank lines, and auto-numbering labels are restored, so a Word test written
with numbered questions and lettered answers needs no re-typing. A blank line is
inserted automatically before any paragraph that starts a question.

A question line starts with a number followed by `.` or `)`. Answer lines start with a
letter followed by `.` or `)`. Case does not matter for keywords.

## Types accepted by Blackboard Ultra and Original

### Multiple choice (MC) and multiple answer (MA)

```
1. Which of the following is a prime number?
a) 4
*b) 5
c) 6
```

One asterisk makes the question multiple choice; two or more make it multiple answer.
Up to 100 answers. No asterisk at all is an error.

### True / false (TF)

```
2. Three is a prime number.
True
```

The single answer line may be `True`, `False`, `T`, or `F`.

### Essay (ESS)

```
3. Tell me your life story.
```

A numbered line with no answers is an essay. To include a sample answer (shown to
graders), use the `essay` keyword; the following lines become the sample:

```
essay 4. Explain why the sky is blue.
Rayleigh scattering of shorter wavelengths.
```

### Fill in the blank (FIB)

```
blank 5. Christmas falls on December _____.
a. 25th
b. 25
```

Every listed answer is accepted as correct. Up to 100 answers.

### Fill in multiple blanks (FIB_PLUS)

Mark each blank in the question text with a variable in square brackets. Give the
accepted answers as `variable. answer` lines. Repeat a label, or separate alternatives
with `|`, for more than one accepted answer. Up to 10 blanks.

```
blanks 6. "Four [a] and [b] years ago" is the beginning of the [c] delivered by [d].
a. score
b. seven
c. Gettysburg Address | The Gettysburg Address
d. Abraham Lincoln
d. Lincoln
```

Variable names may be words (`[city]` with `city. Paris`).

### Matching (MAT)

```
match 7. Match the French and English words:
a. hello / bonjour
b. yes / oui
c. hot / chaud
```

Both sides of every pair are required; Blackboard's upload format cannot express
distractor items.

### Numeric response (NUM)

```
num 8. Approximately how many species of birds are there?
10,000 +/- 1000
```

The tolerance is optional and may also go on a second line (`1000` or `tolerance: 1000`).

## Types accepted by Original course view only

The script rejects these under the default Ultra target and explains why. Use
`--target original` for an Original course.

### Ordering (ORD)

```
order 9. Order the planets from closest to the sun:
Mercury
Earth
Mars
```

Items are listed in the correct order. Labels (`a)`) are optional and stripped.

### Short answer (SR)

```
short 10. Name one cause of the French Revolution.
Financial crisis and food shortages.
```

The lines after the question are the sample answer. Under `--target ultra` this is
written as an essay with the same sample (Ultra has no SR upload type).

### File response (FIL) and opinion scale / Likert (OP)

```
file 11. Upload your completed lab report.

opinion 12. The course workload was reasonable.
```

No answer lines. Blackboard supplies the Likert scale.

### Jumbled sentence (JUMBLED_SENTENCE)

Variables in brackets; `variable. choice` marks the choice that fills that blank;
`-. choice` is a distractor that fills nothing. Listing the same choice text under two
labels makes it correct for both.

```
jumbled 13. The [a] jumped over the [b] dog.
a. fox
b. lazy
-. quick
```

### Quiz bowl (QUIZ_BOWL)

`w.` lines are accepted question words, `p.` lines are accepted answer phrases.

```
quizbowl 14. He delivered the Gettysburg Address.
w. Who
w. Which president
p. Lincoln
p. Abraham Lincoln
```

## Legacy header style (from the original web tool)

A line containing only `MC`, `MA`, `TF`, `BL` (fill in blank) or `ES` (essay) sets the
type for the blocks that follow until a numbered question appears. Answers in this
style have no letters; `*` still marks the correct one.

```
MC
Which of the following is a prime number?
4
*5
6
```

## Common parse errors and fixes

| Report says | Fix |
|---|---|
| "could not be resolved to any known question type" | The first line does not start with `N.` / `N)` or a keyword. Check for a missing number, or a stray line between questions. |
| "invalid answer" | An answer line lacks its `a)` label, or a wrapped line from Word became a separate line. Join it to the answer above. |
| "No correct answer was found" | Add `*` before the correct choice. |
| "Only one answer was found and it was not True or False" | A multiple choice with a single option, or a wrapped question line; add the other choices. |
| Two questions merged into one block | Insert a blank line between them. |
| Question split into two blocks | The script rejoins a lone question line with a following answer block automatically; otherwise remove the blank line. |
| Quotes around a whole question or answer | The script strips them; nothing to do. |
