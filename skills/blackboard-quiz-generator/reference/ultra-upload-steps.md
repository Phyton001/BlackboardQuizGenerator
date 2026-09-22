# Uploading the file into Blackboard

## Ultra course view

1. Open the course and create or open the test (Course Content > + > Create > Test).
2. On the test canvas select the **+** (plus) where you want the questions.
3. Choose **Upload questions from file**.
4. **Browse** to the `.txt` file the script wrote and select it.
5. **Submit**, then **OK**. The questions appear in the test in file order.
6. Set the point value: uploaded questions default to zero points. Select the point box
   on each question, or use the test's settings to apply a value to all.
7. Review each question once. Blackboard skips any row it could not read without
   altering the others, so compare the count with the script's "N of N ready" line.

To build a reusable pool instead: Course Content > Question Banks (or the test's
Reuse questions menu) and use the same **Upload questions from file** option.

## Original course view

1. Control Panel > Course Tools > Tests, Surveys, and Pools > Tests (or Pools).
2. Open the test canvas and select **Upload Questions**.
3. **Browse** to the `.txt` file (written with `--target original`).
4. Optionally enter **Points per question**.
5. **Submit**, then **OK**.

## If the upload complains

- "Invalid question type" on the first line only: re-run with `--bom` removed (default)
  or added; some installations differ in how they read the leading bytes.
- Accented characters garbled: re-run with `--bom`.
- A specific row failed: run `--check` again; the script's validation is stricter than
  Blackboard's parser, but a question edited by hand after export can break it. Fix the
  input file and re-export rather than editing the `.txt` in Word, which may reintroduce
  smart quotes or strip tabs.
