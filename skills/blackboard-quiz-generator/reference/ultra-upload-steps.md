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

## Ultra: import a question bank package (`--format pool`)

Confirmed working in Blackboard Ultra on 22 September 2026 (MC and TF banks).

1. Course Content > Details & Actions > **Manage banks**.
2. **+** > **Import** > **from file** (not the QTI 2.1 option). Choose the `.zip` the
   script wrote. A bank named after `--name` appears; refresh if the list has not
   updated yet. Blackboard emails a log when the import finishes.
3. Open the bank and spot-check one question of each type. An exclamation icon on the
   bank means one or more questions were dropped as unsupported.
4. Points per question were set by `--points`; the question pool in the test can still
   override them.

## Ultra: question banks with a random draw

Ultra's "question bank" is what Original called a pool; Ultra's "question pool" is the
random draw inside a test.

1. If you used `--format txt` instead: Course Content > Details & Actions > **Manage
   banks** > **+** > **New**, title it, save, then inside the bank **+** > **Upload
   questions from file** (if that menu has no upload option on your installation,
   use `--format pool` above, or the fallback at the end).
2. In the test, **+** > **Add question pool** > **Filter** > tick the bank > select the
   questions > **Add Questions**. Set **Number of questions to display** and **Points
   per question** (one value for the whole pool), then **Save**. Repeat per bank.
3. Check the test summary shows the intended question count and total points, turn
   on **Randomize the order of answer options** if no option uses positional wording
   ("all of the above", "A and B only"), then verify in Student Preview.

Partial credit exists only on multiple answer and matching questions in Ultra.

Fallback if a bank's **+** menu has no upload option: create a hidden test per file,
upload into it, and filter the question pool on that test instead. Blackboard blocks
deleting a source test while a pool draws from it, so keep it hidden.

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
