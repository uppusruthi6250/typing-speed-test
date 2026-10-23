import uuid

import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test_results.db"),
        }
    )
    return app.test_client()


def test_home_page_contains_typing_test(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Typing Speed Test" in response.data
    assert b"duration-select" in response.data
    assert b"Previous test results" in response.data


def test_result_page_is_available(client):
    test_id = str(uuid.uuid4())

    response = client.get(f"/results/{test_id}")

    assert response.status_code == 200
    assert b"Your test results" in response.data
    assert b"Passage comparison" in response.data
    assert b"Words to review" in response.data


def get_challenge(client, duration="60"):
    response = client.get(f"/api/challenge?duration={duration}")
    assert response.status_code == 200
    return response.get_json()


def result_payload(challenge, typed_text, duration):
    return {
        "test_id": str(uuid.uuid4()),
        "challenge_id": challenge["challenge_id"],
        "typed_text": typed_text,
        "duration": duration,
    }


def test_challenges_match_selected_duration_and_can_exclude_previous(client):
    short = get_challenge(client, "15")
    next_short = client.get(
        f"/api/challenge?duration=15&exclude={short['challenge_id']}"
    ).get_json()
    long = get_challenge(client, "60")

    assert short["duration"] == 15
    assert next_short["challenge_id"] != short["challenge_id"]
    assert next_short["paragraph"] != short["paragraph"]
    assert long["duration"] == 60
    assert long["challenge_id"] != short["challenge_id"]
    assert len(short["paragraph"].split()) < len(long["paragraph"].split())


def test_minute_based_challenges_scale_to_one_hour(client):
    thirty_minutes = get_challenge(client, "1800")
    one_hour = get_challenge(client, "3600")

    assert thirty_minutes["duration"] == 1800
    assert one_hour["duration"] == 3600
    assert len(thirty_minutes["paragraph"].split()) >= 900
    assert len(one_hour["paragraph"].split()) >= 1800
    assert len(one_hour["paragraph"].split()) > len(thirty_minutes["paragraph"].split())


def test_challenge_rejects_unsupported_duration(client):
    response = client.get("/api/challenge?duration=45")

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_health_endpoint(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_results_start_empty_and_saved_results_are_returned(client):
    challenge = get_challenge(client)
    assert client.get("/api/results").get_json() == []

    response = client.post(
        "/api/results",
        json=result_payload(challenge, challenge["paragraph"], 60),
    )

    assert response.status_code == 201
    assert response.get_json()["correct_chars"] == len(challenge["paragraph"])
    assert response.get_json()["incorrect_chars"] == 0
    assert response.get_json()["accuracy"] == 100
    assert response.get_json()["incorrect_words"] == []
    assert len(client.get("/api/results").get_json()) == 1


def test_saved_result_details_include_passage_and_typed_text(client):
    challenge = get_challenge(client)
    typed_text = "Wrong " + challenge["paragraph"].split(" ", 1)[1]
    test_id = str(uuid.uuid4())
    payload = result_payload(challenge, typed_text, 10)
    payload["test_id"] = test_id
    assert client.post("/api/results", json=payload).status_code == 201

    response = client.get(f"/api/results/{test_id}")

    assert response.status_code == 200
    result = response.get_json()
    assert result["paragraph"] == challenge["paragraph"]
    assert result["typed_text"] == typed_text
    assert result["incorrect_words"][0] == {
        "typed": "Wrong",
        "expected": challenge["paragraph"].split()[0],
    }


def test_unknown_result_details_return_not_found(client):
    response = client.get(f"/api/results/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Test result not found."


def test_scores_are_recomputed_and_incorrect_characters_are_counted(client):
    challenge = get_challenge(client)
    typed_text = "X" + challenge["paragraph"][1:]
    payload = result_payload(challenge, typed_text, 30)
    payload.update({"wpm": 9999, "accuracy": 100})
    response = client.post(
        "/api/results",
        json=payload,
    )

    result = response.get_json()
    assert response.status_code == 201
    assert result["wpm"] == round(len(typed_text) / 5 / 0.5, 2)
    assert result["correct_chars"] == len(challenge["paragraph"]) - 1
    assert result["incorrect_chars"] == 1
    assert result["accuracy"] < 100


def test_result_includes_incorrect_words_and_expected_spelling(client):
    challenge = get_challenge(client)
    expected_words = challenge["paragraph"].split()
    expected_words[0] = "Wrong"

    response = client.post(
        "/api/results",
        json=result_payload(challenge, " ".join(expected_words), 10),
    )

    assert response.status_code == 201
    assert response.get_json()["incorrect_words"][0] == {
        "typed": "Wrong",
        "expected": challenge["paragraph"].split()[0],
    }


def test_word_feedback_handles_an_inserted_word_without_misaligning_following_words(client):
    challenge = get_challenge(client)
    expected_words = challenge["paragraph"].split()
    typed_words = expected_words[:2] + ["extra"] + expected_words[2:]

    response = client.post(
        "/api/results",
        json=result_payload(challenge, " ".join(typed_words), 10),
    )

    assert response.status_code == 201
    assert {
        "typed": "extra",
        "expected": "(extra word)",
    } in response.get_json()["incorrect_words"]
    assert len(response.get_json()["incorrect_words"]) == 1


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {
            "test_id": "not-a-uuid",
            "challenge_id": "short-1",
            "typed_text": "text",
            "duration": 10,
        },
        {
            "test_id": str(uuid.uuid4()),
            "challenge_id": "unknown",
            "typed_text": "text",
            "duration": 10,
        },
        {
            "test_id": str(uuid.uuid4()),
            "challenge_id": "short-1",
            "typed_text": "text",
            "duration": 0,
        },
        {
            "test_id": str(uuid.uuid4()),
            "challenge_id": "short-1",
            "typed_text": "text",
            "duration": 16,
        },
        {
            "test_id": str(uuid.uuid4()),
            "challenge_id": "short-1",
            "typed_text": "text",
            "duration": True,
        },
    ],
)
def test_invalid_result_payload_is_rejected(client, payload):
    response = client.post("/api/results", json=payload)

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_duplicate_test_submission_is_rejected(client):
    challenge = get_challenge(client, "15")
    payload = result_payload(challenge, "hello", 10)
    assert client.post("/api/results", json=payload).status_code == 201

    duplicate = client.post("/api/results", json=payload)

    assert duplicate.status_code == 409
    assert "already" in duplicate.get_json()["error"]
