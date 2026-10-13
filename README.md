# Online Examination Platform

A local SQLite practice/examination app using Python 3.13 and only the standard library. Instructors create exams and author four-option multiple-choice questions with answer feedback. Learners take an exam, and the app validates complete A-D responses, scores them automatically, and shows correctness and instructor feedback.

This is a simple educational tool and **does not provide secure proctoring, identity verification, or anti-cheating controls**. Attempts and answer keys are local records, not a secure assessment service. Do not use it for sensitive student information.

## Run

```powershell
py -3.13 app.py
```

If the Python launcher is unavailable, run with your Python 3.13 executable, for example:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" app.py
```

Choose `Create exam`, then `Add question` for each question, and use `Take exam` to submit an attempt. The first run creates `examinations.sqlite3` in this folder. Student labels are optional and stored only in this local database.

## Tests

```powershell
py -3.13 -m unittest -v
```

No external packages or network connection are needed.
