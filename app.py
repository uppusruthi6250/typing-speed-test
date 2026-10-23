import logging
import os
import random
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from flask import Flask, jsonify, render_template, request


DURATION_OPTIONS = (15, 30, 60, 120, 300, 600, 900, 1800, 2700, 3600)
SENTENCES = (
    "Good habits grow through daily practice and patience.",
    "Clear goals help teams build useful software together.",
    "Small steps can lead to steady progress over time.",
    "Careful work makes reliable results easier to achieve.",
    "Software teams use automation to test each change and share feedback.",
    "Frequent practice helps people improve their speed without losing accuracy.",
    "A clear plan makes a difficult task easier to complete.",
    "Teams learn from mistakes, improve their tools, and deliver better results.",
    "Good communication helps developers solve problems together.",
    "Simple checks can catch errors early and keep an application dependable.",
    "Learning a new skill takes focus and repetition.",
    "Regular practice builds confidence and makes each next step feel easier.",
    "DevOps brings development and operations teams together to deliver reliable software.",
    "Teams build, test, and release small changes while monitoring their applications.",
    "Clear feedback helps everyone find problems early and make the next release safer.",
    "Developers write code, review changes, and use automated checks to find mistakes.",
    "Operations teams monitor running services and share useful feedback.",
    "Working together helps the whole team improve quality.",
    "Keep your hands relaxed, watch the passage, and correct mistakes as you notice them.",
    "Short practice sessions can build a strong habit over time.",
    "Continuous integration gives a team quick feedback whenever code changes.",
    "A pipeline can install dependencies, run tests, and check the application before release.",
    "Containers make it easier to run the same application in different environments.",
    "Persistent storage keeps important records available when a container is replaced or restarted.",
    "Reliable systems are easier to maintain when teams document their decisions.",
    "A thoughtful review can make a small improvement more useful for everyone.",
    "Testing different cases helps reveal unexpected behavior before users find it.",
    "Useful tools should make common tasks simpler and safer to repeat.",
    "A patient approach turns difficult problems into manageable steps.",
    "Consistent feedback helps people understand what to improve next.",
)
MAX_RESULTS = 50


def create_challenge(duration, seed):
    generator = random.Random(seed)
    target_word_count = max(8, round(duration / 2))
    sentences = []
    word_count = 0
    previous_sentence = None
    while word_count < target_word_count:
        choices = [sentence for sentence in SENTENCES if sentence != previous_sentence]
        sentence = generator.choice(choices)
        sentences.append(sentence)
        word_count += len(sentence.split())
        previous_sentence = sentence
    return " ".join(sentences)


def word_key(word):
    return "".join(character for character in word if character.isalnum()).casefold()


def find_incorrect_words(expected_text, typed_text):
    expected_words = expected_text.split()
    typed_words = typed_text.split()
    expected_keys = [word_key(word) for word in expected_words]
    typed_keys = [word_key(word) for word in typed_words]
    matcher = SequenceMatcher(None, expected_keys, typed_keys, autojunk=False)
    incorrect_words = []

    for operation, expected_start, expected_end, typed_start, typed_end in matcher.get_opcodes():
        if operation == "equal":
            continue
        expected_group = expected_words[expected_start:expected_end]
        typed_group = typed_words[typed_start:typed_end]
        paired_count = min(len(expected_group), len(typed_group))
        incorrect_words.extend(
            {"typed": typed_group[index], "expected": expected_group[index]}
            for index in range(paired_count)
        )
        incorrect_words.extend(
            {"typed": typed_word, "expected": "(extra word)"}
            for typed_word in typed_group[paired_count:]
        )
    return incorrect_words


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE_PATH", "data/typing_test.db"),
    )
    if test_config:
        app.config.update(test_config)

    @contextmanager
    def get_db():
        connection = sqlite3.connect(app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize_database():
        database_path = Path(app.config["DATABASE"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with get_db() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS test_results (
                    id TEXT PRIMARY KEY,
                    wpm REAL NOT NULL CHECK (wpm >= 0),
                    accuracy REAL NOT NULL CHECK (accuracy BETWEEN 0 AND 100),
                    correct_chars INTEGER NOT NULL CHECK (correct_chars >= 0),
                    incorrect_chars INTEGER NOT NULL CHECK (incorrect_chars >= 0),
                    duration REAL NOT NULL CHECK (duration > 0),
                    created_at TEXT NOT NULL,
                    challenge_id TEXT,
                    typed_text TEXT
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(test_results)")
            }
            if "challenge_id" not in columns:
                connection.execute("ALTER TABLE test_results ADD COLUMN challenge_id TEXT")
            if "typed_text" not in columns:
                connection.execute("ALTER TABLE test_results ADD COLUMN typed_text TEXT")

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/results/<test_id>")
    def result_page(test_id):
        return render_template("results.html", test_id=test_id)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/challenge")
    def get_challenge():
        requested_duration = request.args.get("duration", "60")
        try:
            duration = int(requested_duration)
        except ValueError:
            return jsonify({"error": "Choose a supported test duration."}), 400
        if duration not in DURATION_OPTIONS:
            return jsonify({"error": "Choose a supported test duration."}), 400

        excluded_id = request.args.get("exclude")
        excluded_paragraph = None
        if excluded_id:
            try:
                excluded_duration_text, excluded_seed_text = excluded_id.split("-", 1)
                excluded_duration = int(excluded_duration_text)
                excluded_seed = int(excluded_seed_text)
            except ValueError:
                pass
            else:
                if excluded_duration == duration and 0 <= excluded_seed < 2**63:
                    excluded_paragraph = create_challenge(duration, excluded_seed)

        while True:
            challenge_id = f"{duration}-{secrets.randbits(63)}"
            seed = int(challenge_id.split("-", 1)[1])
            paragraph = create_challenge(duration, seed)
            if paragraph != excluded_paragraph:
                break
        return jsonify(
            {
                "challenge_id": challenge_id,
                "duration": duration,
                "paragraph": paragraph,
            }
        )

    @app.get("/api/results")
    def get_results():
        try:
            with get_db() as connection:
                rows = connection.execute(
                    """
                    SELECT id, wpm, accuracy, correct_chars, incorrect_chars,
                           duration, created_at
                    FROM test_results
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (MAX_RESULTS,),
                ).fetchall()
            return jsonify([dict(row) for row in rows])
        except sqlite3.Error:
            app.logger.exception("Unable to load typing test results")
            return jsonify({"error": "Unable to load saved results."}), 500

    @app.get("/api/results/<test_id>")
    def get_result(test_id):
        try:
            with get_db() as connection:
                row = connection.execute(
                    """
                    SELECT id, wpm, accuracy, correct_chars, incorrect_chars,
                           duration, created_at, challenge_id, typed_text
                    FROM test_results
                    WHERE id = ?
                    """,
                    (test_id,),
                ).fetchone()
            if row is None:
                return jsonify({"error": "Test result not found."}), 404
            if row["challenge_id"] is None or row["typed_text"] is None:
                return jsonify(
                    {"error": "Detailed results are unavailable for this older test."}
                ), 404

            result = dict(row)
            result["paragraph"] = create_challenge(
                int(row["challenge_id"].split("-", 1)[0]),
                int(row["challenge_id"].split("-", 1)[1]),
            )
            result["incorrect_words"] = find_incorrect_words(
                result["paragraph"],
                result["typed_text"],
            )
            return jsonify(result)
        except sqlite3.Error:
            app.logger.exception("Unable to load typing test result")
            return jsonify({"error": "Unable to load the test result."}), 500

    @app.post("/api/results")
    def save_result():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400

        test_id = payload.get("test_id")
        challenge_id = payload.get("challenge_id")
        typed_text = payload.get("typed_text")
        duration = payload.get("duration")
        if (
            not isinstance(test_id, str)
            or not isinstance(challenge_id, str)
            or not isinstance(typed_text, str)
        ):
            return jsonify({"error": "test_id, challenge_id, and typed_text must be strings."}), 400
        try:
            uuid.UUID(test_id)
        except (ValueError, AttributeError):
            return jsonify({"error": "test_id must be a valid UUID."}), 400
        try:
            challenge_duration_text, seed_text = challenge_id.split("-", 1)
            challenge_duration = int(challenge_duration_text)
            seed = int(seed_text)
        except (ValueError, AttributeError):
            return jsonify({"error": "Unknown challenge. Start a new test and try again."}), 400
        if challenge_duration not in DURATION_OPTIONS or not 0 <= seed < 2**63:
            return jsonify({"error": "Unknown challenge. Start a new test and try again."}), 400
        paragraph = create_challenge(challenge_duration, seed)
        if len(typed_text) > len(paragraph) + 500:
            return jsonify({"error": "Typed text is too long."}), 400
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            return jsonify({"error": "duration must be a number of seconds."}), 400
        if not 0 < duration <= int(challenge_duration):
            return jsonify(
                {"error": f"duration must be greater than 0 and at most {challenge_duration}."}
            ), 400

        correct_chars = sum(
            1
            for index, character in enumerate(typed_text)
            if index < len(paragraph) and character == paragraph[index]
        )
        incorrect_chars = len(typed_text) - correct_chars
        accuracy = (correct_chars / len(typed_text) * 100) if typed_text else 0.0
        wpm = len(typed_text) / 5 / (duration / 60)
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        incorrect_words = find_incorrect_words(paragraph, typed_text)

        try:
            with get_db() as connection:
                connection.execute(
                    """
                    INSERT INTO test_results
                        (id, wpm, accuracy, correct_chars, incorrect_chars, duration,
                         created_at, challenge_id, typed_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        test_id,
                        round(wpm, 2),
                        round(accuracy, 2),
                        correct_chars,
                        incorrect_chars,
                        round(float(duration), 2),
                        created_at,
                        challenge_id,
                        typed_text,
                    ),
                )
        except sqlite3.IntegrityError:
            return jsonify({"error": "This test result has already been submitted."}), 409
        except sqlite3.Error:
            app.logger.exception("Unable to save typing test result")
            return jsonify({"error": "Unable to save the test result."}), 500

        return (
            jsonify(
                {
                    "id": test_id,
                    "wpm": round(wpm, 2),
                    "accuracy": round(accuracy, 2),
                    "correct_chars": correct_chars,
                    "incorrect_chars": incorrect_chars,
                    "incorrect_words": incorrect_words,
                    "duration": round(float(duration), 2),
                    "created_at": created_at,
                    "paragraph": paragraph,
                    "typed_text": typed_text,
                }
            ),
            201,
        )

    initialize_database()
    return app


app = create_app()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5001")), debug=False)
