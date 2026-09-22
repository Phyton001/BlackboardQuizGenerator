#!/usr/bin/env python3
"""
bbquiz.py - convert quiz questions written in Word or plain text into a
Blackboard question upload file (tab-delimited .txt, Ultra or Original
course view).

Python re-implementation of the parsing rules of the Blackboard Quiz
Generator (QuizParser/*.cs in this repository), originally written at
Algonquin College and released under the GNU GPL v3 by Oklahoma Christian
University (https://github.com/OklahomaChristian/BlackboardQuizGenerator).
Extended to every question type in Blackboard's upload format and corrected
for Blackboard Ultra. Standard library only.

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option)
any later version. See the LICENSE file at the repository root.

Usage
-----
    bbquiz.py INPUT [-o OUTPUT] [--target ultra|original] [--format txt|pool]
                    [--points N] [--check] [--allow-invalid] [--bom] [--lf] [--name NAME]

--format txt (default) writes the tab-delimited file for a test's "Upload
questions from file". --format pool writes the zip package that the Question
Banks page imports ("Import > from file"), the same package Original's Pools
page exports.

INPUT is a .txt file in the question format described in
reference/input-format.md, or a Word .docx (read directly, with Word's
auto-numbering labels restored). .doc/.rtf/.odt/.html/.md are converted via
macOS textutil or pandoc when available. Use "-" for stdin.

Exit status: 0 when every question was written, 1 when any question was
invalid (nothing is written unless --allow-invalid), 2 on usage/I-O errors.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

__version__ = "1.0.0"

MAX_BATCH_ULTRA = 250     # Blackboard's recommended maximum records per file
MAX_BATCH_ORIGINAL = 500
MAX_ANSWERS = 100
MAX_FIB_PLUS_VARIABLES = 10


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------
class QType(Enum):
    MC = "Multiple Choice"
    MA = "Multiple Answer"
    TF = "True or False"
    ESSAY = "Essay"
    FIB = "Fill in the Blank"
    FIB_PLUS = "Fill in Multiple Blanks"
    MATCH = "Matching"
    ORDER = "Ordering"
    NUM = "Numeric Response"
    SHORT = "Short Answer"
    FILE = "File Response"
    OPINION = "Opinion Scale / Likert"
    JUMBLED = "Jumbled Sentence"
    QUIZ_BOWL = "Quiz Bowl"
    LEGACY_HEADER = "Question type header"
    UNKNOWN = "Unknown/Invalid"


# Question types each target's upload accepts. Ultra list from
# help.anthology.com "Upload or Import Questions" (Ultra); Original list from
# the Original course view page.
ULTRA_TYPES = {QType.MC, QType.MA, QType.TF, QType.ESSAY, QType.FIB, QType.FIB_PLUS,
               QType.MATCH, QType.NUM}
ORIGINAL_TYPES = ULTRA_TYPES | {QType.ORDER, QType.SHORT, QType.FILE, QType.OPINION,
                                QType.JUMBLED, QType.QUIZ_BOWL}


@dataclass
class Answer:
    text: str
    correct: bool = False
    match: Optional[str] = None   # matching: right-hand side
    var: Optional[str] = None     # fib_plus / jumbled: variable name; quiz bowl: 'w' or 'p'


@dataclass
class Question:
    raw: str
    line: int                      # 1-based line number of the block in the input
    type: QType = QType.UNKNOWN
    number: int = -1
    text: str = ""
    answers: list = field(default_factory=list)
    error: str = ""
    note: str = ""                 # informational message for the report
    tolerance: Optional[str] = None
    sample: str = ""               # essay / short answer sample response

    @property
    def valid(self) -> bool:
        return self.type not in (QType.UNKNOWN, QType.LEGACY_HEADER)

    def fail(self, msg: str) -> "Question":
        self.type = QType.UNKNOWN
        self.error = msg
        return self


# --------------------------------------------------------------------------
# Regular expressions (ported from QuizParser.cs, then extended)
# --------------------------------------------------------------------------
KEYWORDS = ("blanks", "blank", "match", "order", "num", "essay",
            "short", "file", "opinion", "jumbled", "quizbowl")
RX_QUESTION = re.compile(r"^\s*(?P<num>\d+)[\)\.]\s*(?P<text>.+)$")
RX_KEYWORD = re.compile(
    r"^\s*(?P<kw>" + "|".join(KEYWORDS) + r")\s+(?P<num>\d+)[\)\.]\s*(?P<text>.+)$",
    re.IGNORECASE,
)
RX_ANSWER = re.compile(r"^\s*(?P<star>\*)?(?P<id>[a-zA-Z])(?P<sep>[\)\.])\s*(?P<text>.+)$")
# Labelled line whose label may be a word (fill in multiple blanks, jumbled sentence)
RX_VAR_ANSWER = re.compile(r"^\s*(?P<id>[A-Za-z0-9_]+|-)\s*[\)\.:]\s*(?P<text>.+)$")
RX_TRUE_FALSE = re.compile(r"^\s*(?P<tf>t|true|f|false)\s*$", re.IGNORECASE)
RX_NUMERIC = re.compile(
    r"^\s*(?P<value>[-+]?[\d,]*\d(?:\.\d+)?)\s*(?:(?:\+/-|\+-|±)\s*(?P<tol>[\d,]*\d(?:\.\d+)?))?\s*$"
)
RX_BRACKET_VAR = re.compile(r"\[([A-Za-z0-9_]+)\]")

LEGACY_TYPES = {"MC": QType.MC, "MA": QType.MA, "TF": QType.TF, "BL": QType.FIB, "ES": QType.ESSAY}

SMART_CHARS = {
    "“": '"', "”": '"', "„": '"',
    "‘": "'", "’": "'", "‚": "'",
    " ": " ",                 # non-breaking space (Word)
    " ": "\n", " ": "\n",
    "​": "", "﻿": "",    # zero-width space, stray BOM
}


# --------------------------------------------------------------------------
# Text normalisation and block splitting (StringUtils.cs)
# --------------------------------------------------------------------------
def normalise(text: str) -> list[str]:
    for bad, good in SMART_CHARS.items():
        text = text.replace(bad, good)
    text = text.replace("\t", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return [line.strip() for line in text.split("\n")]


def split_blocks(lines: list[str]) -> list[tuple[int, list[str]]]:
    blocks: list[tuple[int, list[str]]] = []
    current: Optional[list[str]] = None
    for i, line in enumerate(lines, 1):
        if line == "":
            current = None
            continue
        if current is None:
            current = []
            blocks.append((i, current))
        current.append(line)
    return blocks


def is_answer_block(lines: list[str]) -> bool:
    if not lines:
        return False
    if len(lines) == 1 and RX_TRUE_FALSE.match(lines[0]):
        return True
    return all(RX_ANSWER.match(line) for line in lines)


def is_question_block(lines: list[str]) -> bool:
    return len(lines) == 1 and bool(RX_QUESTION.match(lines[0]) or RX_KEYWORD.match(lines[0]))


def gather_orphan_answers(blocks: list[tuple[int, list[str]]]) -> list[tuple[int, list[str]]]:
    """Re-join a question line that was separated from its answers by a
    blank line (common when pasting from Word)."""
    if len(blocks) < 2:
        return blocks
    merged = [blocks[0]]
    for i in range(1, len(blocks)):
        if is_answer_block(blocks[i][1]) and is_question_block(blocks[i - 1][1]):
            start, prev_lines = merged[-1]
            merged[-1] = (start, prev_lines + blocks[i][1])
        else:
            merged.append(blocks[i])
    return merged


def unquote(s: str) -> str:
    """CSV-based tools taught authors to wrap fields containing commas in
    double quotes; tab-delimited files do not need that."""
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"' and s.count('"') == 2:
        return s[1:-1].strip()
    return s


# --------------------------------------------------------------------------
# Parser (QuizParser.cs + LegacyParser.cs, extended)
# --------------------------------------------------------------------------
class QuizParser:
    def __init__(self) -> None:
        self.legacy_active: Optional[QType] = None

    def parse(self, text: str) -> list[Question]:
        blocks = gather_orphan_answers(split_blocks(normalise(text)))
        questions: list[Question] = []
        for start, block_lines in blocks:
            q = self.parse_block(start, block_lines)
            if q.type is QType.LEGACY_HEADER:
                continue
            questions.append(q)
        return questions

    def parse_block(self, start: int, lines: list[str]) -> Question:
        q = Question(raw="\n".join(lines), line=start)
        first = lines[0]

        m = RX_QUESTION.match(first)
        if m:
            self.legacy_active = None
            q.number = int(m.group("num"))
            q.text = unquote(m.group("text"))
            return self._parse_default(q, lines[1:])

        m = RX_KEYWORD.match(first)
        if m:
            self.legacy_active = None
            q.number = int(m.group("num"))
            q.text = unquote(m.group("text"))
            handler = getattr(self, "_parse_" + m.group("kw").lower())
            return handler(q, lines[1:])

        return self._parse_legacy(q, lines)

    # -- helpers --------------------------------------------------------------
    def _lettered_answers(self, q: Question, lines: list[str], all_correct: bool,
                          hint: str = "") -> Optional[Question]:
        """Parse 'a) text' lines into q.answers. Returns q (failed) on error."""
        for line in lines:
            m = RX_ANSWER.match(line)
            if not m:
                return q.fail(f"This question has an invalid answer: {line!r}. Answers must "
                              "begin with a letter followed by a period or round bracket."
                              + (" " + hint if hint else ""))
            q.answers.append(Answer(text=unquote(m.group("text")),
                                    correct=all_correct or bool(m.group("star"))))
        if len(q.answers) > MAX_ANSWERS:
            return q.fail(f"Blackboard allows at most {MAX_ANSWERS} answers per question.")
        return None

    @staticmethod
    def _set_true_false(q: Question, token: str) -> Question:
        is_true = token.strip().lower().startswith("t")
        q.type = QType.TF
        q.answers = [Answer("true", is_true), Answer("false", not is_true)]
        return q

    # -- modern format ------------------------------------------------------
    def _parse_default(self, q: Question, answers: list[str]) -> Question:
        if not answers:
            q.type = QType.ESSAY
            return q
        if len(answers) == 1:
            m = RX_TRUE_FALSE.match(answers[0])
            if not m:
                return q.fail("Only one answer was found and it was not True or False. "
                              "Multiple choice questions need two or more lettered answers.")
            return self._set_true_false(q, m.group("tf"))
        if self._lettered_answers(q, answers, all_correct=False):
            return q
        correct = sum(a.correct for a in q.answers)
        if correct == 0:
            return q.fail("No correct answer was found. Put an asterisk (*) in front of the "
                          "correct answer, e.g. '*b) 5'.")
        q.type = QType.MC if correct == 1 else QType.MA
        return q

    def _parse_essay(self, q: Question, answers: list[str]) -> Question:
        q.type = QType.ESSAY
        q.sample = " ".join(answers).strip()
        return q

    def _parse_short(self, q: Question, answers: list[str]) -> Question:
        q.type = QType.SHORT
        q.sample = " ".join(answers).strip()
        return q

    def _parse_file(self, q: Question, answers: list[str]) -> Question:
        q.type = QType.FILE
        if answers:
            return q.fail("File response questions take no answer lines.")
        return q

    def _parse_opinion(self, q: Question, answers: list[str]) -> Question:
        q.type = QType.OPINION
        if answers:
            return q.fail("Opinion/Likert questions take no answer lines; Blackboard supplies "
                          "the scale.")
        return q

    def _parse_blank(self, q: Question, answers: list[str]) -> Question:
        q.type = QType.FIB
        if not answers:
            return q.fail("Fill in the blank questions must list at least one accepted answer.")
        if self._lettered_answers(q, answers, all_correct=True):
            return q
        return q

    def _parse_blanks(self, q: Question, answers: list[str]) -> Question:
        """Fill in multiple blanks: variables in [brackets] in the question
        text; one 'a. answer' line per accepted answer (repeat the label, or
        separate alternatives with '|')."""
        q.type = QType.FIB_PLUS
        variables = []
        for v in RX_BRACKET_VAR.findall(q.text):
            if v not in variables:
                variables.append(v)
        if not variables:
            return q.fail("Fill in multiple blanks questions need each blank marked in the "
                          "question text as a variable in square brackets, e.g. [a] and [b].")
        if len(variables) > MAX_FIB_PLUS_VARIABLES:
            return q.fail(f"Blackboard allows at most {MAX_FIB_PLUS_VARIABLES} blanks.")
        if not answers:
            return q.fail("List the accepted answers, one per line, labelled with the variable "
                          "name, e.g. 'a. score'.")
        seen = []
        for line in answers:
            m = RX_VAR_ANSWER.match(line)
            if not m or m.group("id") == "-":
                return q.fail(f"Invalid answer line {line!r}. Use '<variable>. <answer>'.")
            var = m.group("id")
            if var not in variables:
                return q.fail(f"Answer label '{var}' does not match any [variable] in the "
                              f"question text ({', '.join(variables)}).")
            for alt in m.group("text").split("|"):
                alt = unquote(alt)
                if alt:
                    q.answers.append(Answer(text=alt, correct=True, var=var))
            if var not in seen:
                seen.append(var)
        missing = [v for v in variables if v not in seen]
        if missing:
            return q.fail(f"No answers given for blank(s): {', '.join(missing)}.")
        return q

    def _parse_match(self, q: Question, answers: list[str]) -> Question:
        q.type = QType.MATCH
        if not answers:
            return q.fail("Matching questions must list at least one pair, e.g. 'a. hello / bonjour'.")
        for line in answers:
            m = RX_ANSWER.match(line)
            if not m:
                return q.fail(f"This question has an invalid answer: {line!r}")
            pair = m.group("text")
            if "/" not in pair:
                return q.fail(f"Matching pair {line!r} has no '/' separating the two sides.")
            left, right = pair.split("/", 1)
            q.answers.append(Answer(text=unquote(left), correct=True, match=unquote(right)))
        if len(q.answers) > MAX_ANSWERS:
            return q.fail(f"Blackboard allows at most {MAX_ANSWERS} pairs per question.")
        return q

    def _parse_order(self, q: Question, answers: list[str]) -> Question:
        q.type = QType.ORDER
        items = [line for line in answers if line.strip()]
        if len(items) < 2:
            return q.fail("Ordering questions must list at least two items, one per line, "
                          "in the correct order.")
        if all(RX_ANSWER.match(i) for i in items):   # optional a) b) labels
            items = [RX_ANSWER.match(i).group("text") for i in items]
        q.answers = [Answer(text=unquote(i), correct=True) for i in items]
        return q

    def _parse_num(self, q: Question, answers: list[str]) -> Question:
        q.type = QType.NUM
        if not answers or len(answers) > 2:
            return q.fail("Numeric questions need one answer line, optionally followed by a "
                          "tolerance line, e.g. '4' then '0.5', or '4 +/- 0.5'.")
        m = RX_NUMERIC.match(answers[0])
        if not m:
            return q.fail(f"Numeric answer {answers[0]!r} is not a number.")
        q.answers.append(Answer(text=m.group("value"), correct=True))
        tol = m.group("tol")
        if len(answers) == 2:
            t = re.sub(r"^(tolerance\s*[:=]?\s*|±|\+/-)\s*", "", answers[1].strip(), flags=re.I)
            if not re.fullmatch(r"[\d,]*\d(?:\.\d+)?", t):
                return q.fail(f"Tolerance {answers[1]!r} is not a number.")
            tol = t
        q.tolerance = tol
        return q

    def _parse_jumbled(self, q: Question, answers: list[str]) -> Question:
        """Jumbled sentence: variables in [brackets]; 'a. choice' marks the
        choice that fills [a]; '-. choice' is a distractor. The same choice
        text under two labels fills both."""
        q.type = QType.JUMBLED
        variables = []
        for v in RX_BRACKET_VAR.findall(q.text):
            if v not in variables:
                variables.append(v)
        if not variables:
            return q.fail("Jumbled sentence questions need each blank marked in the question "
                          "text as a variable in square brackets, e.g. [a] and [b].")
        if not answers:
            return q.fail("List the choices, one per line: '<variable>. <choice>' for a correct "
                          "choice, '-. <choice>' for a distractor.")
        choices: dict[str, list[str]] = {}
        order: list[str] = []
        for line in answers:
            m = RX_VAR_ANSWER.match(line)
            if not m:
                return q.fail(f"Invalid choice line {line!r}. Use '<variable>. <choice>' or "
                              "'-. <choice>' for a distractor.")
            var, choice = m.group("id"), unquote(m.group("text"))
            if var != "-" and var not in variables:
                return q.fail(f"Choice label '{var}' does not match any [variable] in the "
                              f"question text ({', '.join(variables)}).")
            if choice not in choices:
                choices[choice] = []
                order.append(choice)
            if var != "-":
                choices[choice].append(var)
        filled = {v for vs in choices.values() for v in vs}
        missing = [v for v in variables if v not in filled]
        if missing:
            return q.fail(f"No choice given for variable(s): {', '.join(missing)}.")
        for choice in order:
            q.answers.append(Answer(text=choice, correct=bool(choices[choice]),
                                    var=" ".join(choices[choice])))
        return q

    def _parse_quizbowl(self, q: Question, answers: list[str]) -> Question:
        """Quiz bowl: 'w. Who' lines are accepted question words, 'p. Lincoln'
        lines are accepted answer phrases."""
        q.type = QType.QUIZ_BOWL
        for line in answers:
            m = RX_VAR_ANSWER.match(line)
            if not m or m.group("id").lower() not in ("w", "p"):
                return q.fail(f"Invalid line {line!r}. Quiz bowl answers are 'w. <question word>' "
                              "or 'p. <answer phrase>'.")
            q.answers.append(Answer(text=unquote(m.group("text")), correct=True,
                                    var=m.group("id").lower()))
        if not any(a.var == "w" for a in q.answers) or not any(a.var == "p" for a in q.answers):
            return q.fail("Quiz bowl questions need at least one 'w.' question word and one "
                          "'p.' answer phrase.")
        return q

    # -- legacy header format (LegacyParser.cs) --------------------------------
    def _parse_legacy(self, q: Question, lines: list[str]) -> Question:
        header = LEGACY_TYPES.get(lines[0].upper())
        if header is not None:
            self.legacy_active = header
            if len(lines) == 1:
                q.type = QType.LEGACY_HEADER
                return q
            body = lines[1:]
        elif self.legacy_active is not None:
            header, body = self.legacy_active, lines
        else:
            return q.fail("This block could not be resolved to any known question type. "
                          "Questions start with a number and a period or bracket (e.g. '1.'), "
                          "or with a keyword such as 'blank 1.' or 'match 1.'.")

        q.type = header
        q.text = unquote(body[0])
        answers = body[1:]

        if header is QType.ESSAY:
            if answers:
                return q.fail("Essay questions must be written on one line and cannot have any "
                              "answers.")
        elif header is QType.FIB:
            if not answers:
                return q.fail("Fill in the blank questions must have at least one answer.")
            q.answers = [Answer(unquote(a), True) for a in answers]
        elif header in (QType.MC, QType.MA):
            if not answers:
                return q.fail(f"{header.value} questions must have at least one answer.")
            for a in answers:
                q.answers.append(Answer(unquote(a[1:]), True) if a.startswith("*")
                                 else Answer(unquote(a), False))
            n = sum(a.correct for a in q.answers)
            if n < 1:
                return q.fail("No correct answers found. Put an asterisk (*) in front of the "
                              "correct answer.")
            if header is QType.MC and n > 1:
                return q.fail("Multiple Choice questions can only have 1 correct answer. Use an "
                              "MA block for multiple answers.")
        elif header is QType.TF:
            if len(answers) != 1 or not RX_TRUE_FALSE.match(answers[0]):
                return q.fail("True or false questions must have exactly one answer line "
                              "reading True or False (or T / F).")
            self._set_true_false(q, answers[0])
        return q


# --------------------------------------------------------------------------
# Writers (Question.cs, corrected and extended for Blackboard)
# --------------------------------------------------------------------------
def _f(s: Optional[str]) -> str:
    """A tab or newline inside a field would break the record."""
    return re.sub(r"[\t\r\n]+", " ", s or "").strip()


def blackboard_record(q: Question, target: str) -> list[str]:
    """Tab-delimited fields for one question. Raises ValueError with an
    explanation when the question cannot be uploaded to this target."""
    t = q.type
    text = _f(q.text)

    if t is QType.SHORT and target == "ultra":
        # Ultra has no separate short-answer upload type; ESS with a sample is the
        # closest equivalent and imports as an Essay question.
        q.note = "Short answer written as ESS (Ultra upload has no SR type)."
        t = QType.ESSAY

    allowed = ULTRA_TYPES if target == "ultra" else ORIGINAL_TYPES
    if t not in allowed:
        code = {QType.ORDER: "ORD", QType.FILE: "FIL", QType.OPINION: "OP",
                QType.JUMBLED: "JUMBLED_SENTENCE", QType.QUIZ_BOWL: "QUIZ_BOWL",
                QType.SHORT: "SR"}.get(t, t.name)
        raise ValueError(
            f"Blackboard Ultra's question upload does not accept {t.value} ({code}) questions. "
            "Create it in the Ultra editor after uploading, or use --target original."
        )

    if t in (QType.MC, QType.MA):
        rec = [t.name, text]
        for a in q.answers:
            rec += [_f(a.text), "correct" if a.correct else "incorrect"]
        return rec
    if t is QType.TF:
        return ["TF", text, "true" if q.answers[0].correct else "false"]
    if t is QType.ESSAY:
        return ["ESS", text] + ([_f(q.sample)] if q.sample else [])
    if t is QType.SHORT:
        return ["SR", text, _f(q.sample)]
    if t is QType.FILE:
        return ["FIL", text]
    if t is QType.OPINION:
        return ["OP", text]
    if t is QType.FIB:
        return ["FIB", text] + [_f(a.text) for a in q.answers]
    if t is QType.FIB_PLUS:
        rec = ["FIB_PLUS", text]
        variables: list[str] = []
        for a in q.answers:
            if a.var not in variables:
                variables.append(a.var)
        groups = []
        for v in variables:
            groups.append([v] + [_f(a.text) for a in q.answers if a.var == v])
        for i, g in enumerate(groups):
            if i:
                rec.append("")            # empty field separates variable groups
            rec += g
        return rec
    if t is QType.MATCH:
        rec = ["MAT", text]
        for a in q.answers:
            left, right = _f(a.text), _f(a.match)
            if not left or not right:
                raise ValueError(
                    "Blackboard matching questions need both sides of every pair (one-to-one); "
                    f"pair '{left} / {right}' has an empty side. Distractor-only items are not "
                    "supported by the upload format."
                )
            rec += [left, right]
        return rec
    if t is QType.NUM:
        rec = ["NUM", text, q.answers[0].text]
        if q.tolerance:
            rec.append(q.tolerance)
        return rec
    if t is QType.ORDER:
        return ["ORD", text] + [_f(a.text) for a in q.answers]
    if t is QType.JUMBLED:
        rec = ["JUMBLED_SENTENCE", text]
        for i, a in enumerate(q.answers):
            if i:
                rec.append("")            # empty field ends the previous choice
            rec.append(_f(a.text))
            rec += a.var.split() if a.var else []
        return rec
    if t is QType.QUIZ_BOWL:
        words = [_f(a.text) for a in q.answers if a.var == "w"]
        phrases = [_f(a.text) for a in q.answers if a.var == "p"]
        return ["QUIZ_BOWL", text] + words + [""] + phrases
    raise ValueError(q.error or "Unknown question type")


# --------------------------------------------------------------------------
# Question pool package writer (Blackboard "x-bb-qti-pool" export format)
#
# This is the zip that Original's Pools page exports and that Ultra's
# Question Banks page imports ("Import > from file"). The structure follows
# Blackboard's own exports as documented by two MIT-licensed tools that
# generate it: toastedcrumpets/BlackboardQuizMaker and bristol-d/bbquiz.
# --------------------------------------------------------------------------
import uuid
import zipfile
import xml.etree.ElementTree as ET

POOL_TYPE_NAMES = {
    QType.MC: "Multiple Choice", QType.MA: "Multiple Answer", QType.TF: "True/False",
    QType.ESSAY: "Essay", QType.SHORT: "Short Response", QType.FIB: "Fill in the Blank",
    QType.FIB_PLUS: "Fill in the Blank Plus", QType.MATCH: "Matching", QType.NUM: "Numeric",
    QType.ORDER: "Ordering", QType.JUMBLED: "Jumbled Sentence",
}
BB_NS = "http://www.blackboard.com/content-packaging/"
XML_NS = "http://www.w3.org/XML/1998/namespace"


class PoolWriter:
    def __init__(self, title: str, points: float = 1.0) -> None:
        self.title = title
        self.points = points
        self._id = 1000000
        self.root = ET.Element("questestinterop")
        assessment = ET.SubElement(self.root, "assessment", title=title)
        self._metadata(assessment, "Assessment")
        rubric = ET.SubElement(assessment, "rubric", view="All")
        self._formatted(ET.SubElement(rubric, "flow_mat", {"class": "Block"}), "")
        pm = ET.SubElement(assessment, "presentation_material")
        self._formatted(ET.SubElement(pm, "flow_mat", {"class": "Block"}), "")
        self.section = ET.SubElement(assessment, "section")
        self._metadata(self.section, "Section")
        self.count = 0

    # -- helpers ----------------------------------------------------------------
    def _next_id(self) -> str:
        self._id += 1
        return f"_{self._id}_1"

    def _metadata(self, node, asitype: str, qtype: str = "Multiple Choice",
                  partial: str = "false", scoremax: Optional[str] = None,
                  numbertype: str = "none", negative: str = "N") -> None:
        md = ET.SubElement(node, asitype.lower() + "metadata")
        for k, v in (
            ("bbmd_asi_object_id", self._next_id()), ("bbmd_asitype", asitype),
            ("bbmd_assessmenttype", "Pool"), ("bbmd_sectiontype", "Subsection"),
            ("bbmd_questiontype", qtype), ("bbmd_is_from_cartridge", "false"),
            ("bbmd_is_disabled", "false"), ("bbmd_negative_points_ind", negative),
            ("bbmd_canvas_fullcrdt_ind", "false"), ("bbmd_all_fullcredit_ind", "false"),
            ("bbmd_numbertype", numbertype), ("bbmd_partialcredit", partial),
            ("bbmd_orientationtype", "vertical"), ("bbmd_is_extracredit", "false"),
            ("qmd_absolutescore_max", scoremax if scoremax is not None else "0"),
            ("qmd_weighting", "0"), ("qmd_instructornotes", ""),
        ):
            ET.SubElement(md, k).text = v

    @staticmethod
    def _formatted(node, text: str):
        material = ET.SubElement(node, "material")
        ext = ET.SubElement(material, "mat_extension")
        ET.SubElement(ext, "mat_formattedtext", type="HTML").text = text
        return material

    def _text_block(self, node, text: str):
        self._formatted(ET.SubElement(node, "flow_mat", {"class": "FORMATTED_TEXT_BLOCK"}), text)

    def _feedback(self, item, ident: str, text: str = "") -> None:
        fb = ET.SubElement(item, "itemfeedback", ident=ident, view="All")
        outer = ET.SubElement(fb, "flow_mat", {"class": "Block"})
        self._text_block(outer, text)

    def _solution(self, item, ident: str, text: str = "") -> None:
        fb = ET.SubElement(item, "itemfeedback", ident=ident, view="All")
        sol = ET.SubElement(fb, "solution", view="All", feedbackstyle="Complete")
        sm = ET.SubElement(sol, "solutionmaterial")
        outer = ET.SubElement(sm, "flow_mat", {"class": "Block"})
        self._text_block(outer, text)

    def _item(self, q: Question, qtype: str, **md):
        self.count += 1
        item = ET.SubElement(self.section, "item", title=f"Question {self.count}", maxattempts="0")
        self._metadata(item, "Item", qtype, scoremax=f"{self.points:.15f}", **md)
        presentation = ET.SubElement(item, "presentation")
        block = ET.SubElement(presentation, "flow", {"class": "Block"})
        qb = ET.SubElement(block, "flow", {"class": "QUESTION_BLOCK"})
        self._formatted(ET.SubElement(qb, "flow", {"class": "FORMATTED_TEXT_BLOCK"}), q.text)
        rb = ET.SubElement(block, "flow", {"class": "RESPONSE_BLOCK"})
        rp = ET.SubElement(item, "resprocessing", scoremodel="SumOfScores")
        ET.SubElement(ET.SubElement(rp, "outcomes"), "decvar", varname="SCORE", vartype="Decimal",
                      defaultval="0", minvalue="0", maxvalue=f"{self.points:.5f}")
        return item, block, rb, rp

    @staticmethod
    def _condition(rp, title: Optional[str] = None):
        rc = ET.SubElement(rp, "respcondition", **({"title": title} if title else {}))
        return rc, ET.SubElement(rc, "conditionvar")

    @staticmethod
    def _score(rc, value: str, feedback: str) -> None:
        ET.SubElement(rc, "setvar", variablename="SCORE", action="Set").text = value
        ET.SubElement(rc, "displayfeedback", linkrefid=feedback, feedbacktype="Response")

    def _incorrect(self, rp) -> None:
        rc, cv = self._condition(rp, "incorrect")
        ET.SubElement(cv, "other")
        self._score(rc, "0", "incorrect")

    def _choice_labels(self, parent, texts: list, shuffle: str = "Yes") -> list:
        ids = []
        for t in texts:
            fl = ET.SubElement(parent, "flow_label", {"class": "Block"})
            ident = uuid.uuid4().hex
            ids.append(ident)
            rl = ET.SubElement(fl, "response_label", ident=ident, shuffle=shuffle,
                               rarea="Ellipse", rrange="Exact")
            self._text_block(rl, t)
        return ids

    # -- question types -----------------------------------------------------------
    def add(self, q: Question) -> None:
        handler = {
            QType.MC: self._mc, QType.MA: self._ma, QType.TF: self._tf, QType.ESSAY: self._essay,
            QType.SHORT: self._short, QType.FIB: self._fib, QType.FIB_PLUS: self._fib_plus,
            QType.MATCH: self._match, QType.NUM: self._num, QType.ORDER: self._order,
            QType.JUMBLED: self._jumbled,
        }.get(q.type)
        if handler is None:
            raise ValueError(f"{q.type.value} questions cannot be written to a question pool "
                             "package; use the tab-delimited text format for them.")
        handler(q)

    def _mc(self, q: Question) -> None:
        item, block, rb, rp = self._item(q, "Multiple Choice")
        lid = ET.SubElement(rb, "response_lid", ident="response", rcardinality="Single", rtiming="No")
        rc_ = ET.SubElement(lid, "render_choice", shuffle="Yes", minnumber="0", maxnumber="0")
        ids = self._choice_labels(rc_, [a.text for a in q.answers])
        correct = ids[[a.correct for a in q.answers].index(True)]
        rc, cv = self._condition(rp, "correct")
        ET.SubElement(cv, "varequal", respident="response", case="No").text = correct
        self._score(rc, "SCORE.max", "correct")
        self._incorrect(rp)
        for ident in ids:
            rc, cv = self._condition(rp)
            ET.SubElement(cv, "varequal", respident=ident, case="No")
            self._score(rc, "100" if ident == correct else "0", ident)
        self._feedback(item, "correct")
        self._feedback(item, "incorrect")
        for ident in ids:
            self._solution(item, ident)

    def _ma(self, q: Question) -> None:
        item, block, rb, rp = self._item(q, "Multiple Answer")
        lid = ET.SubElement(rb, "response_lid", ident="response", rcardinality="Multiple", rtiming="No")
        rc_ = ET.SubElement(lid, "render_choice", shuffle="Yes", minnumber="0", maxnumber="0")
        ids = self._choice_labels(rc_, [a.text for a in q.answers])
        rc, cv = self._condition(rp, "correct")
        and_ = ET.SubElement(cv, "and")
        for ident, a in zip(ids, q.answers):
            parent = and_ if a.correct else ET.SubElement(and_, "not")
            ET.SubElement(parent, "varequal", respident="response", case="No").text = ident
        self._score(rc, "SCORE.max", "correct")
        self._incorrect(rp)
        self._feedback(item, "correct")
        self._feedback(item, "incorrect")
        for ident in ids:
            self._solution(item, ident)

    def _tf(self, q: Question) -> None:
        item, block, rb, rp = self._item(q, "True/False")
        lid = ET.SubElement(rb, "response_lid", ident="response", rcardinality="Single", rtiming="No")
        rc_ = ET.SubElement(lid, "render_choice", shuffle="No", minnumber="0", maxnumber="0")
        fl = ET.SubElement(rc_, "flow_label", {"class": "Block"})
        for word in ("true", "false"):
            rl = ET.SubElement(fl, "response_label", ident=word, shuffle="Yes", rarea="Ellipse", rrange="Exact")
            fm = ET.SubElement(rl, "flow_mat", {"class": "Block"})
            mat = ET.SubElement(fm, "material")
            ET.SubElement(mat, "mattext", charset="us-ascii", texttype="text/plain").text = word
        rc, cv = self._condition(rp, "correct")
        ET.SubElement(cv, "varequal", respident="response", case="No").text = (
            "true" if q.answers[0].correct else "false")
        self._score(rc, "SCORE.max", "correct")
        self._incorrect(rp)
        self._feedback(item, "correct")
        self._feedback(item, "incorrect")

    def _text_response(self, q: Question, qtype: str, rows: str) -> None:
        item, block, rb, rp = self._item(q, qtype)
        rs = ET.SubElement(rb, "response_str", ident="response", rcardinality="Single", rtiming="No")
        ET.SubElement(rs, "render_fib", charset="us-ascii", encoding="UTF_8", rows=rows, columns="127",
                      maxchars="0", prompt="Box", fibtype="String", minnumber="0", maxnumber="0")
        rc, cv = self._condition(rp, "correct")
        self._score(rc, "SCORE.max", "correct")
        self._incorrect(rp)
        self._feedback(item, "correct")
        self._feedback(item, "incorrect")
        self._solution(item, "solution", q.sample)

    def _essay(self, q: Question) -> None:
        self._text_response(q, "Essay", "5")

    def _short(self, q: Question) -> None:
        self._text_response(q, "Short Response", "3")

    def _fib(self, q: Question) -> None:
        item, block, rb, rp = self._item(q, "Fill in the Blank")
        rs = ET.SubElement(rb, "response_str", ident="response", rcardinality="Single", rtiming="No")
        ET.SubElement(rs, "render_fib", charset="us-ascii", encoding="UTF_8", rows="0", columns="0",
                      maxchars="0", prompt="Box", fibtype="String", minnumber="0", maxnumber="0")
        rc, cv = self._condition(rp, "correct")
        or_ = ET.SubElement(cv, "or")
        for a in q.answers:
            ET.SubElement(or_, "varequal", respident="response", case="No").text = a.text
        self._score(rc, "SCORE.max", "correct")
        self._incorrect(rp)
        self._feedback(item, "correct")
        self._feedback(item, "incorrect")

    def _fib_plus(self, q: Question) -> None:
        item, block, rb, rp = self._item(q, "Fill in the Blank Plus")
        variables = []
        for a in q.answers:
            if a.var not in variables:
                variables.append(a.var)
        for v in variables:
            rs = ET.SubElement(rb, "response_str", ident=v, rcardinality="Single", rtiming="No")
            ET.SubElement(rs, "render_fib", charset="us-ascii", encoding="UTF_8", rows="0", columns="0",
                          maxchars="0", prompt="Box", fibtype="String", minnumber="0", maxnumber="0")
        rc, cv = self._condition(rp, "correct")
        and_ = ET.SubElement(cv, "and")
        for v in variables:
            or_ = ET.SubElement(and_, "or")
            for a in q.answers:
                if a.var == v:
                    ET.SubElement(or_, "varequal", respident=v, case="No").text = a.text
        self._score(rc, "SCORE.max", "correct")
        self._incorrect(rp)
        self._feedback(item, "correct")
        self._feedback(item, "incorrect")

    def _num(self, q: Question) -> None:
        item, block, rb, rp = self._item(q, "Numeric")
        rn = ET.SubElement(rb, "response_num", ident="response", rcardinality="Single", rtiming="No")
        ET.SubElement(rn, "render_fib", charset="us-ascii", encoding="UTF_8", rows="0", columns="0",
                      maxchars="0", prompt="Box", fibtype="Decimal", minnumber="0", maxnumber="0")
        answer = float(q.answers[0].text.replace(",", ""))
        tol = float((q.tolerance or "0").replace(",", ""))
        rc, cv = self._condition(rp, uuid.uuid4().hex)
        ET.SubElement(cv, "vargte", respident="response").text = repr(answer - tol)
        ET.SubElement(cv, "varlte", respident="response").text = repr(answer + tol)
        ET.SubElement(cv, "varequal", respident="response", case="No").text = repr(answer)
        ET.SubElement(rc, "displayfeedback", linkrefid="correct", feedbacktype="Response")
        self._incorrect(rp)
        self._feedback(item, "correct")
        self._feedback(item, "incorrect")

    def _order(self, q: Question) -> None:
        import random
        item, block, rb, rp = self._item(q, "Ordering", partial="true", numbertype="letter_lower")
        lid = ET.SubElement(rb, "response_lid", ident="response", rcardinality="Ordered", rtiming="No")
        rc_ = ET.SubElement(lid, "render_choice", shuffle="No", minnumber="0", maxnumber="0")
        ids = [uuid.uuid4().hex for _ in q.answers]
        display = list(range(len(ids)))
        random.shuffle(display)
        for i in display:
            fl = ET.SubElement(rc_, "flow_label", {"class": "Block"})
            rl = ET.SubElement(fl, "response_label", ident=ids[i], shuffle="Yes", rarea="Ellipse", rrange="Exact")
            self._text_block(rl, q.answers[i].text)
        rc, cv = self._condition(rp, "correct")
        and_ = ET.SubElement(cv, "and")
        for ident in ids:
            ET.SubElement(and_, "varequal", respident="response", case="No").text = ident
        self._score(rc, "SCORE.max", "correct")
        self._incorrect(rp)
        self._feedback(item, "correct")
        self._feedback(item, "incorrect")

    def _match(self, q: Question) -> None:
        item, block, rb, rp = self._item(q, "Matching", partial="true", numbertype="letter_upper", negative="Q")
        n = len(q.answers)
        row_ids, choice_ids = [], []
        for a in q.answers:
            row = ET.SubElement(rb, "flow", {"class": "Block"})
            rid = uuid.uuid4().hex
            row_ids.append(rid)
            lid = ET.SubElement(row, "response_lid", ident=rid, rcardinality="Single", rtiming="No")
            rc_ = ET.SubElement(lid, "render_choice", shuffle="Yes", minnumber="0", maxnumber="0")
            fl = ET.SubElement(rc_, "flow_label", {"class": "Block"})
            ids = []
            for _ in q.answers:
                cid = uuid.uuid4().hex
                ids.append(cid)
                ET.SubElement(fl, "response_label", ident=cid, shuffle="Yes", rarea="Ellipse", rrange="Exact")
            choice_ids.append(ids)
            self._formatted(ET.SubElement(row, "flow", {"class": "FORMATTED_TEXT_BLOCK"}), a.text)
        right = ET.SubElement(block, "flow", {"class": "RIGHT_MATCH_BLOCK"})
        for a in q.answers:
            r = ET.SubElement(right, "flow", {"class": "Block"})
            self._formatted(ET.SubElement(r, "flow", {"class": "FORMATTED_TEXT_BLOCK"}), a.match or "")
        for i in range(n):
            rc, cv = self._condition(rp)
            ET.SubElement(cv, "varequal", respident=row_ids[i], case="No").text = choice_ids[i][i]
            ET.SubElement(rc, "setvar", PartialCreditPercent="SCORE", action="Set").text = f"{100 / n:.2f}"
            ET.SubElement(rc, "setvar", NegativeCreditPercent="SCORE", action="Set").text = "0.00"
            ET.SubElement(rc, "displayfeedback", linkrefid="correct", feedbacktype="Response")
        self._incorrect(rp)
        self._feedback(item, "correct")
        self._feedback(item, "incorrect")

    def _jumbled(self, q: Question) -> None:
        item, block, rb, rp = self._item(q, "Jumbled Sentence")
        variables = []
        for a in q.answers:
            for v in (a.var or "").split():
                if v not in variables:
                    variables.append(v)
        option_ids = [uuid.uuid4().hex for _ in q.answers]
        for v in variables:
            lid = ET.SubElement(rb, "response_lid", ident=v, rcardinality="Single", rtiming="No")
            rc_ = ET.SubElement(lid, "render_choice", shuffle="Yes", minnumber="0", maxnumber="0")
            fl = ET.SubElement(rc_, "flow_label", {"class": "Block"})
            for ident, a in zip(option_ids, q.answers):
                rl = ET.SubElement(fl, "response_label", ident=ident, shuffle="Yes", rarea="Ellipse", rrange="Exact")
                fm = ET.SubElement(rl, "flow_mat", {"class": "Block"})
                mat = ET.SubElement(fm, "material")
                ET.SubElement(mat, "mattext", charset="us-ascii", texttype="text/plain").text = a.text
        rc, cv = self._condition(rp, "correct")
        and_ = ET.SubElement(cv, "and")
        for v in variables:
            for ident, a in zip(option_ids, q.answers):
                if v in (a.var or "").split():
                    ET.SubElement(and_, "varequal", respident=v, case="No").text = ident
                    break
        self._score(rc, "SCORE.max", "correct")
        self._incorrect(rp)
        self._feedback(item, "correct")
        self._feedback(item, "incorrect")

    # -- packaging --------------------------------------------------------------
    def package(self) -> bytes:
        import io
        decl = '<?xml version="1.0" encoding="UTF-8"?>\n'
        pool_xml = decl + ET.tostring(self.root, encoding="unicode")
        context = ET.Element("parentContextInfo")
        ET.SubElement(context, "parentContextId").text = "IMPORT"
        context_xml = decl + ET.tostring(context, encoding="unicode")
        ET.register_namespace("bb", BB_NS)
        manifest = ET.Element("manifest", identifier="man00001")
        ET.SubElement(manifest, "organizations")
        resources = ET.SubElement(manifest, "resources")
        for ident, rtype in (("res00001", "assessment/x-bb-qti-pool"),
                             ("res00002", "resource/x-mhhe-course-cx")):
            r = ET.SubElement(resources, "resource", identifier=ident, type=rtype)
            r.set(f"{{{XML_NS}}}base", ident)
            r.set(f"{{{BB_NS}}}file", ident + ".dat")
            r.set(f"{{{BB_NS}}}title", self.title)
        manifest_xml = decl + ET.tostring(manifest, encoding="unicode")
        info = "\n".join((
            "#Bb PackageInfo Property File",
            "cx.package.info.version=6.0",
            "cx.config.operation=blackboard.apps.cx.CxConfig$Operation\\:EXPORT",
            "cx.config.course.id=IMPORT",
            "cx.config.package.identifier=" + uuid.uuid4().hex,
            "cx.config.file.references=false",
            "app.release.number=3800.4.0-rel.40+d78544e",
            "db.product.name=PostgreSQL",
            "java.version=11.0.4",
            "java.default.locale=en",
            "os.name=Linux",
        )) + "\n"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("imsmanifest.xml", manifest_xml)
            z.writestr("res00001.dat", pool_xml)
            z.writestr("res00002.dat", context_xml)
            z.writestr(".bb-package-info", info)
        return buf.getvalue()


def pool_package(questions: list, title: str, points: float = 1.0,
                 target: str = "ultra") -> tuple[bytes, dict]:
    """Build the pool zip from valid questions. Returns (zip bytes, errors by
    question index) so the caller can report questions that were left out."""
    writer = PoolWriter(title, points)
    errors: dict[int, str] = {}
    allowed = ULTRA_TYPES if target == "ultra" else ORIGINAL_TYPES
    for i, q in enumerate(questions):
        if not q.valid:
            continue
        if q.type is QType.SHORT and target == "ultra":
            q.note = "Short answer written as an Essay (Ultra has no short response type)."
            q = Question(raw=q.raw, line=q.line, type=QType.ESSAY, number=q.number, text=q.text,
                         answers=q.answers, sample=q.sample)
        if q.type not in allowed:
            errors[i] = (f"Blackboard Ultra question banks do not accept {q.type.value} questions "
                         "on import; use --target original or create it in the editor.")
            continue
        if q.type is QType.MATCH and any(not (a.text and a.match) for a in q.answers):
            errors[i] = "Matching pairs need both sides for a Blackboard pool."
            continue
        try:
            writer.add(q)
        except ValueError as e:
            errors[i] = str(e)
    return writer.package(), errors


# --------------------------------------------------------------------------
# Input loading: plain text, Word (.docx read directly), other formats via
# textutil (macOS) or pandoc
# --------------------------------------------------------------------------
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _roman(n: int) -> str:
    out, table = "", [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
                      (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    for v, r in table:
        while n >= v:
            out, n = out + r, n - v
    return out


def _fmt_number(n: int, fmt: str) -> str:
    if fmt == "lowerLetter":
        return chr(ord("a") + (n - 1) % 26) * (1 + (n - 1) // 26)
    if fmt == "upperLetter":
        return chr(ord("A") + (n - 1) % 26) * (1 + (n - 1) // 26)
    if fmt == "lowerRoman":
        return _roman(n)
    if fmt == "upperRoman":
        return _roman(n).upper()
    if fmt in ("bullet", "none"):
        return ""
    return str(n)  # decimal and anything else


class _DocxNumbering:
    """Rebuilds the visible labels of Word auto-numbered paragraphs
    (1., a), i. ...) from word/numbering.xml, which the text layer omits."""

    def __init__(self, numbering_xml: Optional[bytes], styles_xml: Optional[bytes]) -> None:
        import xml.etree.ElementTree as ET
        self.levels: dict[str, dict[int, dict]] = {}   # numId -> ilvl -> {start, fmt, text}
        self.style_num: dict[str, tuple[str, int]] = {}
        self.counters: dict[str, dict[int, int]] = {}
        if numbering_xml:
            root = ET.fromstring(numbering_xml)
            abstract: dict[str, dict[int, dict]] = {}
            for an in root.iter(W + "abstractNum"):
                lv = {}
                for l in an.findall(W + "lvl"):
                    ilvl = int(l.get(W + "ilvl", "0"))
                    g = lambda tag, d: (l.find(W + tag).get(W + "val", d)
                                        if l.find(W + tag) is not None else d)
                    lv[ilvl] = {"start": int(g("start", "1") or 1), "fmt": g("numFmt", "decimal"),
                                "text": g("lvlText", "%" + str(ilvl + 1) + ".")}
                abstract[an.get(W + "abstractNumId")] = lv
            for num in root.iter(W + "num"):
                aid = num.find(W + "abstractNumId")
                lv = {k: dict(v) for k, v in abstract.get(aid.get(W + "val") if aid is not None else "", {}).items()}
                for ov in num.findall(W + "lvlOverride"):
                    ilvl = int(ov.get(W + "ilvl", "0"))
                    so = ov.find(W + "startOverride")
                    if so is not None and ilvl in lv:
                        lv[ilvl]["start"] = int(so.get(W + "val", "1"))
                    l = ov.find(W + "lvl")
                    if l is not None:
                        nf, lt = l.find(W + "numFmt"), l.find(W + "lvlText")
                        lv.setdefault(ilvl, {"start": 1, "fmt": "decimal", "text": "%1."})
                        if nf is not None:
                            lv[ilvl]["fmt"] = nf.get(W + "val", "decimal")
                        if lt is not None:
                            lv[ilvl]["text"] = lt.get(W + "val", "%1.")
                self.levels[num.get(W + "numId")] = lv
        if styles_xml:
            root = ET.fromstring(styles_xml)
            for st in root.iter(W + "style"):
                np = st.find(W + "pPr/" + W + "numPr")
                if np is not None and np.find(W + "numId") is not None:
                    ilvl = np.find(W + "ilvl")
                    self.style_num[st.get(W + "styleId")] = (
                        np.find(W + "numId").get(W + "val"),
                        int(ilvl.get(W + "val", "0")) if ilvl is not None else 0)

    def label(self, para) -> str:
        ppr = para.find(W + "pPr")
        num_id, ilvl = None, 0
        if ppr is not None:
            np = ppr.find(W + "numPr")
            if np is not None and np.find(W + "numId") is not None:
                num_id = np.find(W + "numId").get(W + "val")
                il = np.find(W + "ilvl")
                ilvl = int(il.get(W + "val", "0")) if il is not None else 0
            elif ppr.find(W + "pStyle") is not None:
                num_id, ilvl = self.style_num.get(ppr.find(W + "pStyle").get(W + "val"), (None, 0))
        if not num_id or num_id == "0" or num_id not in self.levels:
            return ""
        lv = self.levels[num_id]
        if ilvl not in lv:
            return ""
        c = self.counters.setdefault(num_id, {})
        c[ilvl] = c[ilvl] + 1 if ilvl in c else lv[ilvl]["start"]
        for deeper in [k for k in c if k > ilvl]:
            del c[deeper]
        text = lv[ilvl]["text"]
        if lv[ilvl]["fmt"] in ("bullet", "none"):
            return ""
        for n in range(9, 0, -1):
            if "%" + str(n) in text:
                lvl_n = n - 1
                val = c.get(lvl_n, lv.get(lvl_n, {}).get("start", 1))
                text = text.replace("%" + str(n), _fmt_number(val, lv.get(lvl_n, {}).get("fmt", "decimal")))
        return text + " "


def docx_to_text(path: str) -> str:
    """One line per Word paragraph (empty paragraphs kept as blank lines,
    like pasting from Word into a text box), with auto-numbering labels
    restored. A blank line is also inserted before any paragraph that starts
    a question, since Word authors rarely leave an empty paragraph there."""
    import xml.etree.ElementTree as ET
    import zipfile
    with zipfile.ZipFile(path) as z:
        doc = z.read("word/document.xml")
        numbering = z.read("word/numbering.xml") if "word/numbering.xml" in z.namelist() else None
        styles = z.read("word/styles.xml") if "word/styles.xml" in z.namelist() else None
    numbers = _DocxNumbering(numbering, styles)
    lines: list[str] = []
    for para in ET.fromstring(doc).iter(W + "p"):
        parts = []
        for el in para.iter():
            if el.tag == W + "t":
                parts.append(el.text or "")
            elif el.tag in (W + "tab", W + "br", W + "cr"):
                parts.append(" ")
        text = re.sub(r"\s+", " ", "".join(parts)).strip()
        if text:
            label = numbers.label(para)
            if label and text.startswith("*"):
                # author typed the asterisk inside an auto-lettered item: "b) *5"
                text = "*" + label + text[1:].lstrip()
            else:
                text = label + text
        if text and lines and lines[-1] and (RX_QUESTION.match(text) or RX_KEYWORD.match(text)
                                             or text.upper() in LEGACY_TYPES):
            lines.append("")
        lines.append(text)
    return "\n".join(lines)


def load_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return docx_to_text(path)
    if ext in (".doc", ".rtf", ".odt", ".rtfd", ".html", ".htm", ".md"):
        return convert_to_text(path, ext)
    with open(path, "r", encoding="utf-8-sig") as fh:
        return fh.read()


def convert_to_text(path: str, ext: str) -> str:
    """Convert other document formats to .docx (so numbering survives) and
    read that; fall back to plain-text conversion."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = os.path.join(d, "converted.docx")
        if shutil.which("textutil") and ext in (".doc", ".rtf", ".rtfd", ".odt", ".html", ".htm"):
            r = subprocess.run(["textutil", "-convert", "docx", "-output", tmp, path],
                               capture_output=True, text=True)
            if r.returncode == 0 and os.path.exists(tmp):
                return docx_to_text(tmp)
        if shutil.which("pandoc") and ext != ".doc":
            r = subprocess.run(["pandoc", path, "-o", tmp], capture_output=True, text=True)
            if r.returncode == 0 and os.path.exists(tmp):
                return docx_to_text(tmp)
            r = subprocess.run(["pandoc", path, "-t", "plain", "--wrap=none"],
                               capture_output=True, text=True)
            if r.returncode == 0:
                return r.stdout
    sys.exit(f"Cannot convert {path}: save it as .docx or plain text first.")


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------
def report(questions: list[Question], write_errors: dict[int, str], target: str, stream) -> int:
    ok = 0
    for i, q in enumerate(questions):
        err = q.error if not q.valid else write_errors.get(i, "")
        label = f"Q{q.number}" if q.number > 0 else "block"
        if err:
            print(f"  [FAIL] {label} (input line {q.line}): {err}", file=stream)
            for raw in q.raw.split("\n"):
                print(f"         | {raw}", file=stream)
        else:
            ok += 1
            extra = f", {len(q.answers)} answers" if len(q.answers) > 1 else ""
            note = f"  ({q.note})" if q.note else ""
            print(f"  [ ok ] {label}: {q.type.value}{extra}{note}", file=stream)
    total = len(questions)
    print(f"\n{ok} of {total} question(s) ready.", file=stream)
    limit = MAX_BATCH_ULTRA if target == "ultra" else MAX_BATCH_ORIGINAL
    if total > limit:
        print(f"WARNING: Blackboard recommends at most {limit} questions per upload file. "
              "Consider splitting the input.", file=stream)
    return ok


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]", "", "_".join(name.strip().split()))


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def convert(text: str, target: str = "ultra") -> tuple[list[Question], list[str], dict[int, str]]:
    """Parse text and build output records. Returns (questions, records,
    write_errors keyed by question index)."""
    questions = QuizParser().parse(text)
    records: list[str] = []
    write_errors: dict[int, str] = {}
    for i, q in enumerate(questions):
        if not q.valid:
            continue
        try:
            records.append("\t".join(blackboard_record(q, target)))
        except ValueError as e:
            write_errors[i] = str(e)
    return questions, records, write_errors


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="question text file, .docx, or - for stdin")
    ap.add_argument("-o", "--output", help="output file (default: <input>_<target>.txt or .zip)")
    ap.add_argument("--target", choices=["ultra", "original"], default="ultra",
                    help="Blackboard course view the file is for (default: ultra)")
    ap.add_argument("--format", choices=["txt", "pool"], default="txt",
                    help="txt: tab-delimited file for 'Upload questions from file' in a test; "
                         "pool: zip package for 'Import' on the Question Banks page (default: txt)")
    ap.add_argument("--points", type=float, default=1.0,
                    help="points per question stored in a pool package (default: 1)")
    ap.add_argument("--name", help="quiz name; used for the default output file name")
    ap.add_argument("--check", action="store_true", help="validate and report only; write nothing")
    ap.add_argument("--allow-invalid", action="store_true",
                    help="write the valid questions even if some are invalid")
    ap.add_argument("--bom", action="store_true",
                    help="prefix the file with a UTF-8 byte-order mark (Blackboard's sample "
                         "file has none; try this only if accented characters import wrongly)")
    ap.add_argument("--lf", action="store_true",
                    help="use Unix line endings instead of Windows CRLF")
    ap.add_argument("--version", action="version", version=__version__)
    args = ap.parse_args(argv)

    try:
        text = load_text(args.input)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    questions, records, write_errors = convert(text, args.target)
    if not questions:
        print("No questions found in the input.", file=sys.stderr)
        return 1

    pool_bytes = b""
    if args.format == "pool":
        stem = "quiz" if args.input == "-" else os.path.splitext(os.path.basename(args.input))[0]
        pool_bytes, write_errors = pool_package(questions, args.name or stem, args.points, args.target)

    print(f"bbquiz {__version__} - target: {args.target}, format: {args.format}", file=sys.stderr)
    report(questions, write_errors, args.target, sys.stderr)
    failed = sum(1 for q in questions if not q.valid) + len(write_errors)

    if args.check:
        return 1 if failed else 0
    if failed and not args.allow_invalid:
        print("Nothing written. Fix the questions above (or pass --allow-invalid to write only "
              "the valid ones).", file=sys.stderr)
        return 1

    ext = ".zip" if args.format == "pool" else ".txt"
    if args.output:
        out_path = args.output
    else:
        base = safe_name(args.name) if args.name else ""
        if not base:
            stem = "quiz" if args.input == "-" else os.path.splitext(os.path.basename(args.input))[0]
            base = f"{stem}_{args.target}"
        out_dir = "." if args.input == "-" else os.path.dirname(os.path.abspath(args.input))
        out_path = os.path.join(out_dir, base + ext)

    if args.format == "pool":
        if failed:
            # rebuild without the failed questions
            pool_bytes, _ = pool_package([q for i, q in enumerate(questions)
                                          if q.valid and i not in write_errors],
                                         args.name or os.path.splitext(os.path.basename(out_path))[0],
                                         args.points, args.target)
        with open(out_path, "wb") as fh:
            fh.write(pool_bytes)
        records = [q for i, q in enumerate(questions) if q.valid and i not in write_errors]
    else:
        body = "\n".join(records)              # no trailing blank line: Blackboard rejects it
        newline = "\n" if args.lf else "\r\n"
        encoding = "utf-8-sig" if args.bom else "utf-8"
        with open(out_path, "w", encoding=encoding, newline=newline) as fh:
            fh.write(body)
    print(f"Wrote {len(records)} question(s) to {out_path}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
