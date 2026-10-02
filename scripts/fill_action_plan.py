#!/usr/bin/env python3
"""Task 2 - Fill the Action Plan template.

Copies the instructor's Action Plan template to deliverables/ and fills the
content cells. The template's fonts, colours, table layout and page setup are
preserved: content paragraphs are cloned from the template's own placeholder
paragraphs, and only the text and the placeholder-grey colour are changed.

Run:  python3 scripts/fill_action_plan.py
"""

import copy
import os
import shutil
import sys

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.environ.get(
    "TEMPLATES_DIR", "/home/hadoop/capstone/templates"
)
TEMPLATE = os.path.join(
    TEMPLATES_DIR, "SIC_Big Data_Capstone Project_Action Plan.docx"
)
OUT = os.path.join(PROJECT_ROOT, "deliverables", "Action_Plan.docx")

PLACEHOLDER_GREY = "A6A6A6"
BODY_BLACK = "000000"


def set_cell_lines(cell, lines):
    """Replace a content cell with `lines`, reusing the template's formatting.

    The first paragraph of the cell acts as a style donor: its font (SamsungOne
    400), size (14pt) and indentation are cloned for every new line. Two
    properties are deliberately adjusted:

    * colour: the placeholder grey is forced to solid black, and the theme
      shading attributes are dropped so Word cannot re-derive the grey;
    * letter-spacing: the template condenses runs by 0.6pt (`w:spacing=-12`),
      which makes LibreOffice collapse the spaces on any line that fills the
      column - "Vàng A Ký (Team Leader)" renders as "VàngAKý(TeamLeader)".
      Removing it from our own content runs is a 0.6pt typographic change and
      makes the document render correctly outside Microsoft Word.
    """
    donor = copy.deepcopy(cell.paragraphs[0]._p)

    for p in list(cell.paragraphs):
        p._p.getparent().remove(p._p)

    if not lines:
        lines = [""]

    for line in lines:
        new_p = copy.deepcopy(donor)
        runs = new_p.findall(qn("w:r"))

        # Keep a single run and rewrite its text.
        for extra in runs[1:]:
            new_p.remove(extra)

        if runs:
            run = runs[0]
            for t in run.findall(qn("w:t")):
                run.remove(t)
            t = OxmlElement("w:t")
            t.set(qn("xml:space"), "preserve")
            t.text = line
            run.append(t)

            rPr = run.find(qn("w:rPr"))
            if rPr is not None:
                spacing = rPr.find(qn("w:spacing"))
                if spacing is not None:
                    rPr.remove(spacing)

                color = rPr.find(qn("w:color"))
                if color is not None:
                    color.set(qn("w:val"), BODY_BLACK)
                    for attr in ("w:themeColor", "w:themeShade", "w:themeTint"):
                        if color.get(qn(attr)) is not None:
                            del color.attrib[qn(attr)]

        cell._tc.append(new_p)


# --------------------------------------------------------------------------
# Content (English, per the course convention)
# --------------------------------------------------------------------------

TEAM_NAME = "Team 6"

TEAM_LEADER_MEMBERS = [
    "Vàng A Ký /",
    "Nguyễn Đình Bằng, Vàng Thị Dẳm, Dương Thị Hạnh, Ngô Lương Nguyên",
]

PROJECT_TITLE = (
    "SentimentGuard: Real-time Sentiment Classification of Live Chat Comments "
    "for Early Detection of Harmful Comment Spikes"
)

GOAL = [
    "Build a real-time pipeline that classifies live chat comments as negative, "
    "neutral or positive using Apache Kafka and Spark Structured Streaming.",
    "Detect a spike of negative comments within a short time window and alert the "
    "streamer while the session is still running.",
    "Train and evaluate a Spark ML text classifier, reporting macro-F1 and per-class "
    "precision, recall and F1.",
    "Deliver a low-cost, self-hosted prototype that a streamer with no moderation "
    "team can run on commodity hardware.",
    "State clearly which results come from replayed data and which guarantees remain "
    "unverified.",
]

ABSTRACT = (
    "Live chat moves far faster than a solo streamer can read, so harmful comment "
    "spikes are usually noticed only after the damage is done. This project builds a "
    "real-time sentiment classification pipeline: comments are ingested through Apache "
    "Kafka, processed by Spark Structured Streaming with event-time windows and "
    "watermarks, and scored by a Spark ML model into negative, neutral and positive. "
    "Results are aggregated per one-minute window and an alert is raised when the "
    "negative ratio crosses a configurable threshold. Because labelled live chat is "
    "not publicly available and platform terms restrict retaining user comments, the "
    "model is trained on a public labelled comment dataset and the live stream is "
    "reproduced by replaying that data through Kafka."
)

METHOD = (
    "The project follows a five-stage pipeline: Kafka ingestion, Spark Structured "
    "Streaming transformation, Spark ML classification, Spark SQL query and insight, "
    "and Streamlit visualization. Text cleaning is implemented once in a shared module "
    "and reused by both the training and the streaming code, so the two cannot drift "
    "apart. The classifier is a Spark ML Pipeline chaining tokenization, stop-word "
    "removal, n-grams and TF-IDF with a linear model, with TF-IDF fitted only on the "
    "training split to prevent leakage. Duplicate and near-duplicate comments are "
    "removed before the train/validation/test split, the test set is used once at the "
    "end, and class imbalance is handled with class weights."
)

DATA = (
    "The model is trained on a public labelled dataset of online comments with three "
    "sentiment classes; the exact source and licence are recorded before any reported "
    "result uses it. Live chat comments are not publicly available with sentiment "
    "labels, and platform terms restrict retaining user comments, so the live stream "
    "is simulated: the labelled dataset is replayed through Kafka at a configurable "
    "rate, with random bursts and a small share of deliberately late records to "
    "exercise watermarking and the dead-letter queue. Labels never enter the stream; "
    "they are stored separately and joined back by comment ID only for evaluation. "
    "User identifiers are replaced with salted hashes and no personal data is retained."
)

EXPECTED_OUTCOME = (
    "The prototype is expected to classify comments in near real time and to raise an "
    "alert within seconds of a harmful comment spike, with end-to-end latency reported "
    "at p50, p95 and p99. Model quality will be reported as macro-F1 with per-class "
    "precision, recall and F1, alongside measured throughput and the results of "
    "restarting the job mid-stream. The benefit is for people who stream alone and "
    "cannot afford commercial moderation tools: an early warning lets them slow the "
    "chat, enable moderation mode or step away before a spike escalates. Because the "
    "tool is self-hosted, no comment data leaves the operator's own machine."
)

ROLE_BY_MEMBER = [
    "Vàng A Ký (Team Leader) - project management, schedule and WBS, report and slide "
    "coordination, integration testing.",
    "Nguyễn Đình Bằng - Kafka data engineer: broker setup, topics, replay producer, "
    "ingestion throughput measurement.",
    "Vàng Thị Dẳm - streaming engineer: Structured Streaming job, event-time windows, "
    "watermark, dead-letter queue, fault tolerance.",
    "Dương Thị Hạnh - machine learning engineer: data preparation, Spark ML pipeline, "
    "model training and evaluation.",
    "Ngô Lương Nguyên - data analyst: Spark SQL queries, visualization, Streamlit "
    "dashboard, insights.",
]

SCHEDULE_SUMMARY = [
    "Phase 1 (Day 1-5) - Planning: team building, action plan, WBS, topic framing and "
    "data selection, preliminary presentation.",
    "Phase 2 (Day 6-11) - Prototype: Kafka and Spark setup, ingestion, training data "
    "preparation, Spark ML model, Structured Streaming job, queries and dashboard, "
    "prototype presentation.",
    "Phase 3 (Day 12-20) - Refinement and delivery: benchmarking, fault-tolerance "
    "testing, model tuning, usage scenario, final report and final presentation.",
    "The detailed day-by-day plan is maintained in the accompanying WBS workbook, "
    "reviewed on Day 9, Day 14 and Day 19.",
]


def main():
    if not os.path.exists(TEMPLATE):
        sys.exit(f"Template not found: {TEMPLATE}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    shutil.copyfile(TEMPLATE, OUT)

    doc = Document(OUT)
    t0, t1, t2 = doc.tables[0], doc.tables[1], doc.tables[2]

    set_cell_lines(t0.rows[1].cells[1], [TEAM_NAME])
    set_cell_lines(t0.rows[2].cells[1], TEAM_LEADER_MEMBERS)
    set_cell_lines(t0.rows[3].cells[1], [PROJECT_TITLE])
    set_cell_lines(t0.rows[5].cells[0], GOAL)
    set_cell_lines(t0.rows[7].cells[0], [ABSTRACT])
    set_cell_lines(t0.rows[9].cells[0], [METHOD])

    set_cell_lines(t1.rows[1].cells[0], [DATA])
    set_cell_lines(t1.rows[3].cells[0], [EXPECTED_OUTCOME])
    set_cell_lines(t1.rows[5].cells[0], ROLE_BY_MEMBER)

    set_cell_lines(t2.rows[1].cells[0], SCHEDULE_SUMMARY)
    # Comment & Assessment is left blank for the instructor.
    set_cell_lines(t2.rows[3].cells[0], [""])

    doc.save(OUT)
    print(f"written: {OUT}")

    check = Document(OUT)
    for i, t in enumerate(check.tables):
        print(f"\n--- TABLE {i} ---")
        for ri, row in enumerate(t.rows):
            seen = []
            for c in row.cells:
                if c._tc not in [x._tc for x in seen]:
                    seen.append(c)
            for c in seen:
                txt = c.text.strip()
                print(f"  r{ri}: {txt[:100]!r}" + (" ..." if len(txt) > 100 else ""))


if __name__ == "__main__":
    main()
