(() => {
    const passageElement = document.getElementById("passage");
    const durationSelect = document.getElementById("duration-select");
    const input = document.getElementById("typing-input");
    const timerElement = document.getElementById("timer");
    const correctCount = document.getElementById("correct-count");
    const incorrectCount = document.getElementById("incorrect-count");
    const startButton = document.getElementById("start-button");
    const finishButton = document.getElementById("finish-button");
    const restartButton = document.getElementById("restart-button");
    const message = document.getElementById("message");
    const resultsPanel = document.getElementById("results-panel");
    const wordFeedback = document.getElementById("word-feedback");
    const wordFeedbackList = document.getElementById("word-feedback-list");
    const historyMessage = document.getElementById("history-message");
    const resultsBody = document.getElementById("results-body");

    let state = "ready";
    let startedAt = 0;
    let deadline = 0;
    let timerInterval = null;
    let testId = "";
    let challenge = null;
    let challengeRequest = 0;

    function currentPassage() {
        return challenge ? challenge.paragraph : "";
    }

    function setMessage(element, text, kind = "") {
        element.textContent = text;
        element.className = `message${kind ? ` is-${kind}` : ""}`;
    }

    function formatTime(totalSeconds) {
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;
        if (hours > 0) {
            return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
        }
        if (minutes > 0) {
            return `${minutes}:${String(seconds).padStart(2, "0")}`;
        }
        return String(seconds);
    }

    function measure(text, duration) {
        const passage = currentPassage();
        let correct = 0;
        for (let index = 0; index < text.length; index += 1) {
            if (index < passage.length && text[index] === passage[index]) {
                correct += 1;
            }
        }
        return {
            wpm: text.length / 5 / (duration / 60),
            accuracy: text.length ? (correct / text.length) * 100 : 0,
            correct_chars: correct,
            incorrect_chars: text.length - correct,
        };
    }

    function updateLiveCounts() {
        const metrics = measure(input.value, 60);
        correctCount.textContent = metrics.correct_chars;
        incorrectCount.textContent = metrics.incorrect_chars;
    }

    function renderMetrics(metrics) {
        document.getElementById("result-wpm").textContent = Number(metrics.wpm).toFixed(2);
        document.getElementById("result-accuracy").textContent = `${Number(metrics.accuracy).toFixed(2)}%`;
        document.getElementById("result-correct").textContent = metrics.correct_chars;
        document.getElementById("result-incorrect").textContent = metrics.incorrect_chars;
        resultsPanel.hidden = false;
    }

    function renderWordFeedback(incorrectWords) {
        wordFeedbackList.replaceChildren();
        for (const item of incorrectWords) {
            const listItem = document.createElement("li");
            const typed = document.createElement("span");
            typed.className = "incorrect-word";
            typed.textContent = item.typed;
            const expected = document.createElement("span");
            expected.className = "expected-word";
            expected.textContent = item.expected;
            listItem.append(typed, document.createTextNode(" → "), expected);
            wordFeedbackList.append(listItem);
        }
        wordFeedback.hidden = false;
        if (incorrectWords.length === 0) {
            wordFeedbackList.textContent = "No incorrectly typed words. Great work!";
        }
    }

    function findIncorrectWords(typedText) {
        const typedWords = typedText.trim() ? typedText.trim().split(/\s+/) : [];
        const expectedWords = currentPassage().split(/\s+/);
        return typedWords
            .map((typed, index) => ({
                typed,
                expected: expectedWords[index] || "(no word expected)",
            }))
            .filter((item, index) => index >= expectedWords.length || item.typed !== expectedWords[index]);
    }

    async function loadChallenge(excludeCurrent = true) {
        const requestId = ++challengeRequest;
        const selectedDuration = durationSelect.value;
        const query = new URLSearchParams({ duration: selectedDuration });
        if (excludeCurrent && challenge && challenge.duration === Number(selectedDuration)) {
            query.set("exclude", challenge.challenge_id);
        }
        startButton.disabled = true;
        durationSelect.disabled = true;
        setMessage(message, "Loading a fresh passage...");
        try {
            const response = await fetch(`/api/challenge?${query}`);
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Unable to load a typing passage.");
            }
            if (requestId !== challengeRequest) {
                return;
            }
            challenge = result;
            passageElement.textContent = challenge.paragraph;
            passageElement.dataset.challengeId = challenge.challenge_id;
            timerElement.textContent = formatTime(challenge.duration);
            timerElement.setAttribute("aria-label", `${challenge.duration} seconds remaining`);
            startButton.disabled = false;
            setMessage(message, "");
        } catch (error) {
            if (requestId === challengeRequest) {
                setMessage(message, error.message || "Unable to load a typing passage.", "error");
            }
        } finally {
            if (requestId === challengeRequest) {
                durationSelect.disabled = false;
            }
        }
    }

    function renderHistory(results) {
        resultsBody.replaceChildren();
        for (const result of results) {
            const row = document.createElement("tr");
            const date = new Date(result.created_at);
            const values = [
                Number.isNaN(date.getTime()) ? result.created_at : date.toLocaleString(),
                Number(result.wpm).toFixed(2),
                `${Number(result.accuracy).toFixed(2)}%`,
                result.correct_chars,
                result.incorrect_chars,
            ];
            for (const value of values) {
                const cell = document.createElement("td");
                cell.textContent = value;
                row.append(cell);
            }
            resultsBody.append(row);
        }
        setMessage(
            historyMessage,
            results.length ? "" : "No previous results yet."
        );
    }

    async function loadHistory() {
        try {
            const response = await fetch("/api/results");
            if (!response.ok) {
                throw new Error("The server could not load saved results.");
            }
            renderHistory(await response.json());
        } catch (error) {
            setMessage(historyMessage, error.message || "Unable to load saved results.", "error");
        }
    }

    async function finishTest() {
        if (state !== "running") {
            return;
        }
        state = "completed";
        window.clearInterval(timerInterval);
        timerInterval = null;
        input.disabled = true;
        startButton.disabled = true;
        finishButton.disabled = true;
        durationSelect.disabled = true;
        const duration = Math.max(
            0.01,
            Math.min(challenge.duration, (performance.now() - startedAt) / 1000)
        );
        const metrics = measure(input.value, duration);
        renderMetrics(metrics);
        wordFeedback.hidden = true;
        setMessage(message, "Test complete. Saving your result...");

        try {
            const response = await fetch("/api/results", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    test_id: testId,
                    challenge_id: challenge.challenge_id,
                    typed_text: input.value,
                    duration,
                }),
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "The result could not be saved.");
            }
            window.location.assign(`/results/${encodeURIComponent(result.id)}`);
        } catch (error) {
            renderMetrics(metrics);
            renderWordFeedback(findIncorrectWords(input.value));
            setMessage(
                message,
                `Your score is shown, but it could not be saved: ${error.message || "server unavailable"}`,
                "error"
            );
        }
    }

    function updateTimer() {
        const remaining = Math.max(0, Math.ceil((deadline - performance.now()) / 1000));
        timerElement.textContent = formatTime(remaining);
        timerElement.setAttribute("aria-label", `${remaining} seconds remaining`);
        if (remaining === 0) {
            finishTest();
        }
    }

    function startTest() {
        if (state !== "ready" || !challenge) {
            return;
        }
        state = "running";
        startedAt = performance.now();
        deadline = startedAt + challenge.duration * 1000;
        testId = crypto.randomUUID();
        input.disabled = false;
        input.focus();
        startButton.disabled = true;
        finishButton.disabled = false;
        durationSelect.disabled = true;
        restartButton.disabled = false;
        setMessage(message, "The test has started. Good luck!");
        timerInterval = window.setInterval(updateTimer, 200);
    }

    function restartTest() {
        if (state === "loading") {
            return;
        }
        window.clearInterval(timerInterval);
        timerInterval = null;
        state = "ready";
        startedAt = 0;
        deadline = 0;
        testId = "";
        input.value = "";
        input.disabled = true;
        startButton.disabled = true;
        finishButton.disabled = true;
        restartButton.disabled = true;
        durationSelect.disabled = false;
        timerElement.textContent = formatTime(Number(durationSelect.value));
        timerElement.setAttribute("aria-label", `${durationSelect.value} seconds remaining`);
        correctCount.textContent = "0";
        incorrectCount.textContent = "0";
        resultsPanel.hidden = true;
        wordFeedback.hidden = true;
        loadChallenge(true);
    }

    input.addEventListener("input", () => {
        updateLiveCounts();
        if (state === "running" && input.value.length >= currentPassage().length) {
            finishTest();
        }
    });
    startButton.addEventListener("click", startTest);
    finishButton.addEventListener("click", finishTest);
    restartButton.addEventListener("click", restartTest);
    durationSelect.addEventListener("change", () => {
        if (state === "ready") {
            loadChallenge(false);
        }
    });

    loadChallenge(false);
    loadHistory();
})();
