"""Local multiple-choice examination platform (not a proctoring system)."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

LABELS = ("A", "B", "C", "D")


class ExaminationPlatform:
    def __init__(self, database="examinations.sqlite3"):
        self.database = str(database)
        self.initialize()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def initialize(self):
        with self.connect() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS exams (
                    id INTEGER PRIMARY KEY, title TEXT NOT NULL CHECK(length(trim(title)) > 0),
                    description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY, exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
                    prompt TEXT NOT NULL CHECK(length(trim(prompt)) > 0), options TEXT NOT NULL,
                    correct_option INTEGER NOT NULL CHECK(correct_option BETWEEN 0 AND 3), feedback TEXT NOT NULL DEFAULT '');
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY, exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
                    student_label TEXT NOT NULL, score INTEGER NOT NULL, total INTEGER NOT NULL,
                    submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS answers (
                    attempt_id INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
                    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                    selected_option INTEGER NOT NULL CHECK(selected_option BETWEEN 0 AND 3),
                    is_correct INTEGER NOT NULL CHECK(is_correct IN (0,1)), PRIMARY KEY(attempt_id, question_id));""")

    def create_exam(self, title, description=""):
        title = title.strip()
        if not title:
            raise ValueError("Exam title is required")
        with self.connect() as db:
            return db.execute("INSERT INTO exams (title, description) VALUES (?, ?)", (title, description.strip())).lastrowid

    def add_question(self, exam_id, prompt, options, correct_option, feedback=""):
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Question prompt is required")
        options = [str(item).strip() for item in options]
        if len(options) != 4 or any(not item for item in options):
            raise ValueError("Each question must have exactly four non-empty options")
        if isinstance(correct_option, str):
            selected = correct_option.strip().upper()
            if selected not in LABELS:
                raise ValueError("Correct option must be A, B, C, or D")
            correct_index = LABELS.index(selected)
        elif isinstance(correct_option, int) and 0 <= correct_option <= 3:
            correct_index = correct_option
        else:
            raise ValueError("Correct option must be A, B, C, or D")
        with self.connect() as db:
            if db.execute("SELECT 1 FROM exams WHERE id=?", (exam_id,)).fetchone() is None:
                raise KeyError(f"No exam with ID {exam_id}")
            return db.execute("INSERT INTO questions (exam_id, prompt, options, correct_option, feedback) VALUES (?, ?, ?, ?, ?)",
                              (exam_id, prompt, json.dumps(options), correct_index, feedback.strip())).lastrowid

    def list_exams(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT e.*, COUNT(q.id) AS question_count FROM exams e LEFT JOIN questions q ON q.exam_id=e.id GROUP BY e.id ORDER BY e.id")]

    def get_questions(self, exam_id):
        with self.connect() as db:
            if db.execute("SELECT 1 FROM exams WHERE id=?", (exam_id,)).fetchone() is None:
                raise KeyError(f"No exam with ID {exam_id}")
            return [dict(row) | {"options": json.loads(row["options"])} for row in db.execute(
                "SELECT id, exam_id, prompt, options, feedback FROM questions WHERE exam_id=? ORDER BY id", (exam_id,))]

    def submit_attempt(self, exam_id, answers, student_label="Student"):
        label = student_label.strip()
        if not label:
            raise ValueError("Student label is required")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM exams WHERE id=?", (exam_id,)).fetchone() is None:
                raise KeyError(f"No exam with ID {exam_id}")
            questions = db.execute("SELECT id, correct_option FROM questions WHERE exam_id=? ORDER BY id", (exam_id,)).fetchall()
            if not questions:
                raise ValueError("This exam has no questions yet")
            expected = {row["id"] for row in questions}
            normalized = {}
            try:
                for key, value in answers.items():
                    question_id = int(key)
                    choice = value.strip().upper() if isinstance(value, str) else value
                    index = LABELS.index(choice) if isinstance(choice, str) and choice in LABELS else choice
                    if question_id in normalized or not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < 4:
                        raise ValueError
                    normalized[question_id] = index
            except (TypeError, ValueError) as exc:
                raise ValueError("Answers must use a valid A-D choice for each question") from exc
            if set(normalized) != expected:
                raise ValueError("Provide exactly one answer for every question in the exam")
            score = sum(normalized[row["id"]] == row["correct_option"] for row in questions)
            cursor = db.execute("INSERT INTO attempts (exam_id, student_label, score, total) VALUES (?, ?, ?, ?)",
                                (exam_id, label, score, len(questions)))
            attempt_id = cursor.lastrowid
            db.executemany("INSERT INTO answers (attempt_id, question_id, selected_option, is_correct) VALUES (?, ?, ?, ?)",
                           [(attempt_id, row["id"], normalized[row["id"]], int(normalized[row["id"]] == row["correct_option"])) for row in questions])
        return self.get_attempt(attempt_id)

    def get_attempt(self, attempt_id):
        with self.connect() as db:
            row = db.execute("SELECT a.*, e.title AS exam_title FROM attempts a JOIN exams e ON e.id=a.exam_id WHERE a.id=?", (attempt_id,)).fetchone()
            if row is None:
                raise KeyError(f"No attempt with ID {attempt_id}")
            result = dict(row)
            result["answers"] = [dict(item) | {"selected_label": LABELS[item["selected_option"]], "correct_label": LABELS[item["correct_option"]]}
                                 for item in db.execute("""SELECT q.id AS question_id, q.prompt, q.feedback, q.correct_option,
                                     a.selected_option, a.is_correct FROM answers a JOIN questions q ON q.id=a.question_id
                                     WHERE a.attempt_id=? ORDER BY q.id""", (attempt_id,))]
            return result


def main():
    platform = ExaminationPlatform()
    while True:
        print("\nExaminations | 1 List  2 Create exam  3 Add question  4 Take exam  0 Exit")
        choice = input("> ").strip()
        try:
            if choice == "0":
                break
            if choice == "1":
                for exam in platform.list_exams():
                    print(f"#{exam['id']} {exam['title']} ({exam['question_count']} questions) — {exam['description']}")
            elif choice == "2":
                print(f"Created exam #{platform.create_exam(input('Title: '), input('Description (optional): '))}")
            elif choice == "3":
                exam_id = int(input("Exam ID: "))
                prompt = input("Question: ")
                options = [input(f"{label}: ") for label in LABELS]
                correct = input("Correct option (A-D): ")
                feedback = input("Feedback shown after submission (optional): ")
                print(f"Added question #{platform.add_question(exam_id, prompt, options, correct, feedback)}")
            elif choice == "4":
                for exam in platform.list_exams():
                    print(f"#{exam['id']} {exam['title']} ({exam['question_count']} questions)")
                exam_id = int(input("Exam ID: "))
                student = input("Name/label for local results (optional): ").strip() or "Student"
                questions = platform.get_questions(exam_id)
                responses = {}
                for question in questions:
                    print(f"\n{question['prompt']}")
                    for label, option in zip(LABELS, question["options"]):
                        print(f"  {label}) {option}")
                    responses[question["id"]] = input("Your answer (A-D): ")
                result = platform.submit_attempt(exam_id, responses, student)
                print(f"\nResult: {result['score']}/{result['total']}")
                for answer in result["answers"]:
                    status = "Correct" if answer["is_correct"] else f"Incorrect; correct answer: {answer['correct_label']}"
                    print(f"{answer['prompt']} — {status}")
                    if answer["feedback"]:
                        print(f"  Feedback: {answer['feedback']}")
            else:
                print("Choose one of the listed options.")
        except (ValueError, KeyError) as exc:
            print(f"Could not complete request: {exc}")


if __name__ == "__main__":
    main()
