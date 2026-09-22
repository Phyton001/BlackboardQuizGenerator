"""Tests for bbquiz.py. Run with:  python3 -m unittest discover -s tests -v"""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import bbquiz  # noqa: E402
from bbquiz import QType, QuizParser, convert  # noqa: E402

SCRIPT = os.path.join(ROOT, "scripts", "bbquiz.py")
EXAMPLES = os.path.join(ROOT, "examples")


def read(name):
    with open(os.path.join(EXAMPLES, name), encoding="utf-8") as fh:
        return fh.read()


def parse(text):
    return QuizParser().parse(text)


def records(text, target="ultra"):
    qs, recs, errs = convert(text, target)
    return recs, errs, qs


class ParserTests(unittest.TestCase):
    def test_multiple_choice_and_answer(self):
        qs = parse("1. Q?\na) 4\n*b) 5\nc) 6\n\n2. Q?\n*a) 2\n*b) 3\nc) 4")
        self.assertEqual([q.type for q in qs], [QType.MC, QType.MA])
        self.assertEqual([a.correct for a in qs[0].answers], [False, True, False])

    def test_true_false_and_essay(self):
        qs = parse("1. Three is prime.\nTrue\n\n2. Life story.\n\n3. Sky is blue.\nF")
        self.assertEqual([q.type for q in qs], [QType.TF, QType.ESSAY, QType.TF])
        self.assertTrue(qs[0].answers[0].correct)
        self.assertTrue(qs[2].answers[1].correct)

    def test_keyword_types(self):
        text = read("all_types_ultra.txt")
        qs = parse(text)
        self.assertEqual(
            [q.type for q in qs],
            [QType.MC, QType.MA, QType.TF, QType.ESSAY, QType.ESSAY, QType.FIB,
             QType.FIB_PLUS, QType.MATCH, QType.NUM],
        )
        self.assertTrue(all(q.valid for q in qs), [q.error for q in qs])

    def test_orphan_answers_are_rejoined(self):
        qs = parse("1. Q?\n\na) 4\n*b) 5")
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0].type, QType.MC)

    def test_legacy_header_format(self):
        qs = parse("MC\nWhich is prime?\n4\n*5\n6\n\nTF\nThree is prime.\nT\n\nBL\nTwo plus two is ___.\nfour\n4")
        self.assertEqual([q.type for q in qs], [QType.MC, QType.TF, QType.FIB])
        self.assertEqual(qs[0].answers[1].text, "5")

    def test_legacy_header_applies_to_following_blocks(self):
        qs = parse("MC\n\nWhich is prime?\n4\n*5\n\nWhich is even?\n*4\n5")
        self.assertEqual([q.type for q in qs], [QType.MC, QType.MC])

    def test_legacy_single_line_essay_under_header(self):
        # The original C# treated any one-line block as a header; this was a bug.
        qs = parse("ES\n\nTell me your life story.")
        self.assertEqual([q.type for q in qs], [QType.ESSAY])

    def test_errors(self):
        qs = parse("1. Q?\na) 4\nb) 5\n\n1. Q?\nmaybe\n\nblah blah")
        self.assertFalse(any(q.valid for q in qs))
        self.assertIn("asterisk", qs[0].error)
        self.assertIn("True or False", qs[1].error)
        self.assertIn("could not be resolved", qs[2].error)

    def test_word_artifacts_are_normalised(self):
        qs = parse("1.\tWhat is “two” plus two?\n*a)\t4\nb) 5")
        self.assertEqual(qs[0].text, 'What is "two" plus two?')
        self.assertEqual(qs[0].answers[0].text, "4")

    def test_wrapped_quotes_are_unwrapped(self):
        qs = parse('1. "Determining a, b, and c?"\n*a) "Yes, indeed"\nb) No')
        self.assertEqual(qs[0].text, "Determining a, b, and c?")
        self.assertEqual(qs[0].answers[0].text, "Yes, indeed")

    def test_fib_plus_validation(self):
        qs = parse("blanks 1. The [a] is red.\nb. apple")
        self.assertIn("does not match", qs[0].error)
        qs = parse("blanks 1. The [a] and [b].\na. apple")
        self.assertIn("No answers given for blank(s): b", qs[0].error)

    def test_numeric_forms(self):
        qs = parse("num 1. Q\n4\n\nnum 2. Q\n4 +/- 0.5\n\nnum 3. Q\n10,000\n1000")
        self.assertEqual([(q.answers[0].text, q.tolerance) for q in qs],
                         [("4", None), ("4", "0.5"), ("10,000", "1000")])


class BlackboardWriterTests(unittest.TestCase):
    def test_ultra_records(self):
        text = read("all_types_ultra.txt")
        recs, errs, _ = records(text, "ultra")
        self.assertEqual(errs, {})
        self.assertEqual(recs[0], "MC\tWhich of the following is a prime number?\t4\tincorrect\t5\tcorrect\t6\tincorrect")
        self.assertEqual(recs[1].split("\t")[0], "MA")
        self.assertEqual(recs[2], "TF\tThree is a prime number.\ttrue")
        self.assertEqual(recs[3], "ESS\tTell me your life story.")
        self.assertEqual(recs[4], "ESS\tExplain why the sky is blue.\tRayleigh scattering of shorter wavelengths.")
        self.assertEqual(recs[5], "FIB\tChristmas falls on December _____.\t25th\t25")
        self.assertEqual(
            recs[6],
            'FIB_PLUS\t"Four [a] and [b] years ago" is the beginning of the [c] delivered by [d].'
            "\ta\tscore\t\tb\tseven\t\tc\tGettysburg Address\tThe Gettysburg Address"
            "\t\td\tAbraham Lincoln\tLincoln",
        )
        self.assertEqual(recs[7], "MAT\tMatch the French and English words:\thello\tbonjour\tyes\toui\thot\tchaud")
        self.assertEqual(recs[8], "NUM\tApproximately how many species of birds are there?\t10,000\t1000")

    def test_original_only_types(self):
        text = read("original_only_types.txt")
        recs, errs, qs = records(text, "original")
        self.assertEqual(errs, {})
        self.assertEqual(recs[0], "ORD\tOrder the planets from closest to the sun to farthest:\tMercury\tEarth\tMars\tJupiter")
        self.assertEqual(recs[1], "SR\tName one cause of the French Revolution.\tFinancial crisis and food shortages.")
        self.assertEqual(recs[2], "FIL\tUpload your completed lab report.")
        self.assertEqual(recs[3], "OP\tThe course workload was reasonable.")
        self.assertEqual(recs[4], "JUMBLED_SENTENCE\tThe [a] jumped over the [b] dog.\tfox\ta\t\tlazy\tb\t\tquick")
        self.assertEqual(recs[5], "QUIZ_BOWL\tHe delivered the Gettysburg Address.\tWho\tWhich president\t\tLincoln\tAbraham Lincoln")

    def test_ultra_rejects_original_only_types_but_maps_short_answer(self):
        text = read("original_only_types.txt")
        recs, errs, qs = records(text, "ultra")
        self.assertEqual(sorted(errs), [0, 2, 3, 4, 5])
        self.assertIn("ORD", errs[0])
        self.assertEqual(recs, ["ESS\tName one cause of the French Revolution.\tFinancial crisis and food shortages."])
        self.assertIn("Ultra", qs[1].note)

    def test_matching_requires_both_sides_for_blackboard(self):
        recs, errs, _ = records("match 1. Q\na. 3 / three\nb. 4 /", "ultra")
        self.assertIn("empty side", errs[0])

    def test_ordering_labels_are_stripped(self):
        recs, errs, _ = records("order 1. Q\na) one\nb) two", "original")
        self.assertEqual(recs[0], "ORD\tQ\tone\ttwo")

    def test_lowercase_flags_english(self):
        recs, _, _ = records("1. Q\n*a) x\nb) y\n\n2. Q\nfalse")
        self.assertIn("\tcorrect", recs[0])
        self.assertTrue(recs[1].endswith("\tfalse"))




DOCX_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def make_docx(path, paragraphs):
    """Minimal .docx. paragraphs: list of (text, numId|None, ilvl). numId 1 is a
    decimal '%1.' list, numId 2 a lowerLetter '%1)' list; both start at 1."""
    import zipfile
    body = ""
    for text, num_id, ilvl in paragraphs:
        ppr = (f"<w:pPr><w:numPr><w:ilvl w:val=\"{ilvl}\"/><w:numId w:val=\"{num_id}\"/>"
               "</w:numPr></w:pPr>") if num_id else ""
        run = f"<w:r><w:t xml:space=\"preserve\">{text}</w:t></w:r>" if text else ""
        body += f"<w:p>{ppr}{run}</w:p>"
    document = f'<?xml version="1.0" encoding="UTF-8"?><w:document {DOCX_W}><w:body>{body}</w:body></w:document>'
    numbering = (f'<?xml version="1.0" encoding="UTF-8"?><w:numbering {DOCX_W}>'
                 '<w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/>'
                 '<w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl></w:abstractNum>'
                 '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:start w:val="1"/>'
                 '<w:numFmt w:val="lowerLetter"/><w:lvlText w:val="%1)"/></w:lvl></w:abstractNum>'
                 '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>'
                 '<w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>'
                 '<w:num w:numId="3"><w:abstractNumId w:val="1"/>'
                 '<w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>'
                 '</w:numbering>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("word/document.xml", document)
        z.writestr("word/numbering.xml", numbering)


class DocxTests(unittest.TestCase):
    def test_auto_numbering_labels_and_blank_lines_are_restored(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "quiz.docx")
            make_docx(path, [
                ("Which is prime?", 1, 0),      # 1.
                ("4", 2, 0),                    # a)
                ("*5", 2, 0),                   # b)  (asterisk typed by the author)
                ("6", 2, 0),                    # c)
                ("", None, 0),                  # empty paragraph
                ("Which is even?", 1, 0),       # 2.
                ("*4", 3, 0),                   # a)  new list, restarts
                ("5", 3, 0),                    # b)
                ("Three is prime.", 1, 0),      # 3.  no empty paragraph before it
                ("True", None, 0),
            ])
            text = bbquiz.docx_to_text(path)
            self.assertEqual(text.split("\n"), [
                "1. Which is prime?", "a) 4", "*b) 5", "c) 6", "",
                "2. Which is even?", "*a) 4", "b) 5", "",
                "3. Three is prime.", "True",
            ])
            qs = parse(text)
            self.assertEqual([q.type for q in qs], [QType.MC, QType.MC, QType.TF])
            self.assertTrue(qs[0].answers[1].correct)

    def test_docx_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "quiz.docx")
            make_docx(path, [("Life story.", 1, 0), ("", None, 0), ("The sky is blue.", 1, 0), ("T", None, 0)])
            out = os.path.join(d, "out.txt")
            r = subprocess.run([sys.executable, SCRIPT, path, "-o", out], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out, "rb") as fh:
                self.assertEqual(fh.read(), b"ESS\tLife story.\r\nTF\tThe sky is blue.\ttrue")


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)

    def test_file_conventions_match_blackboard_sample(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "out.txt")
            r = self.run_cli(os.path.join(EXAMPLES, "all_types_ultra.txt"), "-o", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out, "rb") as fh:
                data = fh.read()
            self.assertFalse(data.startswith(b"\xef\xbb\xbf"), "no BOM by default")
            self.assertIn(b"\r\n", data, "CRLF line endings")
            self.assertFalse(data.endswith(b"\n"), "no trailing blank line")
            self.assertEqual(data.count(b"\r\n"), 8)
            self.assertIn("9 of 9 question(s) ready", r.stderr)

    def test_invalid_input_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "q.txt")
            with open(src, "w") as fh:
                fh.write("1. Q\na) x\nb) y")
            r = self.run_cli(src, "-o", os.path.join(d, "out.txt"))
            self.assertEqual(r.returncode, 1)
            self.assertFalse(os.path.exists(os.path.join(d, "out.txt")))
            self.assertIn("[FAIL] Q1", r.stderr)

    def test_check_mode_and_stdin(self):
        r = subprocess.run([sys.executable, SCRIPT, "-", "--check"], input="1. Q\nTrue",
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("True or False", r.stderr)

    def test_bom_and_lf_flags(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "out.txt")
            r = self.run_cli(os.path.join(EXAMPLES, "all_types_ultra.txt"), "-o", out, "--bom", "--lf")
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out, "rb") as fh:
                data = fh.read()
            self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\r\n", data)


if __name__ == "__main__":
    unittest.main()
