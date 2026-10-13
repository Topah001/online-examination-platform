import tempfile
import unittest
from pathlib import Path
from app import ExaminationPlatform


class ExaminationPlatformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.platform = ExaminationPlatform(Path(self.temp.name) / "test.sqlite3")
        self.exam = self.platform.create_exam("Science", "Basics")
        self.q1 = self.platform.add_question(self.exam, "2 + 2?", ["1", "2", "4", "5"], "C", "Addition")
        self.q2 = self.platform.add_question(self.exam, "Sky color?", ["Blue", "Green", "Red", "Black"], "A")

    def tearDown(self):
        self.temp.cleanup()

    def test_create_and_list_exams(self):
        exams = self.platform.list_exams()
        self.assertEqual(exams[0]["title"], "Science")
        self.assertEqual(exams[0]["question_count"], 2)

    def test_questions_do_not_reveal_answers(self):
        question = self.platform.get_questions(self.exam)[0]
        self.assertEqual(question["options"], ["1", "2", "4", "5"])
        self.assertNotIn("correct_option", question)

    def test_submission_scores_and_returns_feedback(self):
        result = self.platform.submit_attempt(self.exam, {self.q1: "C", self.q2: "B"}, "Learner")
        self.assertEqual((result["score"], result["total"], result["student_label"]), (1, 2, "Learner"))
        self.assertTrue(result["answers"][0]["is_correct"])
        self.assertEqual(result["answers"][0]["feedback"], "Addition")
        self.assertEqual(result["answers"][1]["correct_label"], "A")

    def test_validates_completeness_and_choice(self):
        for answers in ({self.q1: "C"}, {self.q1: "Z", self.q2: "A"}, {self.q1: "A", self.q2: "A", 999: "B"}):
            with self.subTest(answers=answers), self.assertRaises(ValueError):
                self.platform.submit_attempt(self.exam, answers)

    def test_validates_authoring(self):
        with self.assertRaises(ValueError):
            self.platform.create_exam(" ")
        with self.assertRaises(ValueError):
            self.platform.add_question(self.exam, "Prompt", ["one", "two"], "A")
        with self.assertRaises(ValueError):
            self.platform.add_question(self.exam, "Prompt", ["1", "2", "3", "4"], "E")
        with self.assertRaises(KeyError):
            self.platform.add_question(404, "Prompt", ["1", "2", "3", "4"], "A")

    def test_unknown_exam_and_attempt_raise(self):
        with self.assertRaises(KeyError):
            self.platform.submit_attempt(404, {})
        with self.assertRaises(KeyError):
            self.platform.get_attempt(404)


if __name__ == "__main__":
    unittest.main()
