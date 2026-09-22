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

## Who uses this tool: lineage and hosts

Compiled 22 September 2026 by checking each site and the GitHub fork lists. "Hosts"
means the institution runs its own copy; "links to" means its faculty help pages point
staff at someone else's copy. Lineage marked *inferred* rests on identical page text or
code rather than a printed credit.

### The lineage

1. **College of Southern Idaho** (Twin Falls, Idaho) wrote the original *CSI Blackboard
   Quiz Generator*, live at csi.edu from at least February 2006 until 2017. CSI moved to
   Canvas in 2016 and published the source under MIT in 2019, marked unmaintained.
   <https://github.com/college-of-southern-idaho/blackboard-quiz-generator>
2. **Algonquin College** (Ottawa) built its *Blackboard Test Generator* in 2012 on the
   CSI design, adding the `QuizParser` library, and later rebuilt it for Brightspace.
   Today: <https://lmsquizgenerator.algonquincollege.com/> (Brightspace only, CC BY-NC-SA)
   and <https://github.com/alexling850/LMSQuizGenerator> (no licence file).
3. **Oklahoma Christian University** (Edmond, Oklahoma) received Algonquin's Blackboard
   code, hosts it at <https://ed.oc.edu/blackboardquizgenerator/Default.aspx>, and
   released it under GPL v3 in 2020: <https://github.com/OklahomaChristian/BlackboardQuizGenerator>.
   This repository is a fork of that release.

### Institutions hosting a version

| Institution | Derived from | URL | Notes |
|---|---|---|---|
| College of Southern Idaho | origin | <https://www.csi.edu/bbquiz/default.aspx> | Notice page only; tool retired 2017 |
| Algonquin College | origin of the C# version | <https://lmsquizgenerator.algonquincollege.com/> | Live; Brightspace CSV |
| Oklahoma Christian University | Algonquin | <https://ed.oc.edu/blackboardquizgenerator/Default.aspx> | Live; Blackboard test .txt and pool .zip |
| Bentley University | Oklahoma Christian (credited) | <https://atc4.bentley.edu/BBQuiz/> | Live; Blackboard |
| Carleton University | Algonquin (credited) | <https://tls.carleton.ca/brightspace/quiz/generator/> | Live; Brightspace |
| University of Texas Rio Grande Valley | Oklahoma Christian (*inferred*) | <https://webapps.utrgv.edu/aa/coltt/quiz-generator/> | Live; Brightspace |
| Daemen University | CSI (*inferred*, help text verbatim) | <https://bbtest.daemen.edu/> | Live; Blackboard Original pools and Ultra banks |
| SUNY Cortland | unconfirmed | <https://webapp.cortland.edu/BlackboardQuizGenerator/> | Live; "Blackboard Quiz Builder" |
| Inter American University of Puerto Rico, Ponce | CSI (static copy of the repo files) | <https://ponce.inter.edu/ed/convert/> | Files only, not a running tool |

### Institutions that point staff at one of these copies

| Institution | Points to | URL |
|---|---|---|
| Humber College | Oklahoma Christian | <https://humber.ca/facultyblackboard/knowledgebase/creating-question-banks-in-blackboard-ultra/> |
| Seneca Polytechnic | Oklahoma Christian | <https://employees.senecapolytechnic.ca/spaces/266/blackboard-ultra/articles/assessing-learning/17819/creating-question-banks-using-a-test-generator> |
| Georgian College | Oklahoma Christian | <https://georgiancollege.helpjuice.com/en_US/assessments/ocu-blackboard-test-generator> |
| Northern Illinois University | Oklahoma Christian and CSI | <https://www.niu.edu/blackboard/guides/tips-for-assessing-student-learning.shtml> |
| The American College of Greece | Oklahoma Christian | <https://web.acg.edu/web/blackboard/assessments/blackboard-learn-test-question-generators/> |
| SUNY Oneonta | Oklahoma Christian | <https://facultycenter.openlab.oneonta.edu/2020/04/30/a-faster-way-to-get-your-test-questions-into-blackboard-finally/> |
| Youngstown State University | Oklahoma Christian | <https://ysu.edu/sites/default/files/users/atkaufman/Blackboard%20Ultra%20Test%20Creation%20and%20Questions%20Import.pdf> |
| University of Arkansas | Oklahoma Christian (and its own tool, "inspired by" it) | <https://tips.uark.edu/blackboard-learn-ultra-test-question-formatter/> |
| Southern Methodist University | CSI (2008, earliest dated reference) | <https://blog.smu.edu/academictechnology/blackboard-quiz-generator/> |
| California Baptist University | CSI | <https://calbaptist.edu/about/offices/center-for-faculty-development/teaching/technology-for-education/documents/Blackboard-Quiz-Generator.pdf> |
| Stark State College | CSI | <https://efaculty.starkstate.edu/wp-content/uploads/2018/12/Bb-Test-Pool-Generator.pdf> |
| University of Hartford | CSI | <https://www.hartford.edu/faculty-staff/faculty/fcld/_files/731041-ConvertingTestBanksforBb_Q22018.pdf> |
| Eastern Kentucky University | CSI | bbhelp.eku.edu (site now offline) |
| College of DuPage | CSI, Algonquin, NWTC, BYU-Idaho (comparison page) | cod.edu/it/blackboard/testgenerators.htm (page since removed) |
| University of Limerick | Carleton | <https://www.ul.ie/brightspace/articles/quiz-question-generator-from-carleton-university> |
| Xavier University of Louisiana | Algonquin | <https://cat.xula.edu/food/brightspace-tip-608-test-quiz-question-generator/> |
| BMCC, City University of New York | Carleton | <https://openlab.bmcc.cuny.edu/bmcc-lms-transition/2023/12/20/quizzes/> |
| East Stroudsburg University | Algonquin (video) | <https://www.youtube.com/watch?v=ecSTmw10hzg> |

### Independent tools with the same purpose

| Tool | Institution or author | URL | Notes |
|---|---|---|---|
| Blackboard Test Generator | Northeast Wisconsin Technical College | <https://github.com/nwtc-edu/blackboard-test-generator> | Different input format; unmaintained |
| DEET Blackboard Ultra Test Generator | Central Texas College | <https://github.com/stevenchadburrow/BlackboardTestGenerator> | ColdFusion site; C++ command-line version, public domain |
| LIU Blackboard Quiz Converter | Long Island University | <https://webapps2.liu.edu/bbquiz/> | Browser-only JavaScript |
| Blackboard Exam Formatter | University of Arkansas | <https://tips.uark.edu/blackboard-learn-ultra-test-question-formatter/> | Ultra; 2026 |
| Quiz Question Converter | Minnesota State | <https://mnsite.learn.minnstate.edu/shared/quizConverter/index.html> | Brightspace |
| bbquiz | University of Bristol | <https://github.com/bristol-d/bbquiz> | MIT; writes the pool package format this skill uses |
| BlackboardQuizMaker | Marcus Bannerman | <https://github.com/toastedcrumpets/BlackboardQuizMaker> | MIT; Python, LaTeX and images; pool package format |
| bbquizmaster | Philip Walker, University of Leeds | <https://github.com/WoosterUK/bbquizmaster> | GPL v3; JavaScript |
| bbquizgen | Hannah Dee, Aberystwyth University | <https://github.com/handee/bbquizgen> | Python |
| bbquiz | Giovanni Sileno, University of Amsterdam / VU | <https://github.com/gsileno/bbquiz> | Java, 2015 |
| blackboard-test-generator | Joshua Eckroth, Stetson University | <https://github.com/joshuaeckroth/blackboard-test-generator> | MIT; Perl, 2014 |

### GitHub forks

Oklahoma Christian's repository has 27 forks and CSI's 16, none owned by an institution
and none carrying substantive changes. Individual fork owners list Queen Mary University
of London, Universidad de Alcalá, University of Groningen, the Emirates College for
Advanced Education, and Cape Peninsula University of Technology.

## The original site

The following question types are available in the ASP.NET site: multiple choice,
multiple answer, true/false, essay, fill in the blank, matching. It consists of `.aspx`
pages in C# and the `QuizParser` Visual Studio solution that handles parsing and output.
Pull requests and suggestions welcome.
