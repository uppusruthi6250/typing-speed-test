(() => {
    const testId = document.body.dataset.testId;
    const message = document.getElementById("result-message");
    const details = document.getElementById("result-details");
    const expectedText = document.getElementById("expected-text");
    const typedText = document.getElementById("typed-text");
    const correctionList = document.getElementById("correction-list");
    const noCorrections = document.getElementById("no-corrections");

    function setMessage(text, kind = "") {
        message.textContent = text;
        message.className = `message${kind ? ` is-${kind}` : ""}`;
    }

    function renderComparison(expected, typed) {
        expectedText.replaceChildren();
        typedText.replaceChildren();
        const length = Math.max(expected.length, typed.length);

        for (let index = 0; index < length; index += 1) {
            if (index < expected.length) {
                const character = document.createElement("span");
                character.className = index >= typed.length
                    ? "missing-character"
                    : expected[index] === typed[index]
                        ? "correct-character"
                        : "incorrect-character";
                character.textContent = expected[index];
                expectedText.append(character);
            }
            if (index < typed.length) {
                const character = document.createElement("span");
                character.className = index >= expected.length || expected[index] !== typed[index]
                    ? "incorrect-character"
                    : "correct-character";
                character.textContent = typed[index];
                typedText.append(character);
            }
        }
    }

    function renderCorrections(items) {
        correctionList.replaceChildren();
        for (const item of items) {
            const listItem = document.createElement("li");
            const typedWord = document.createElement("span");
            typedWord.className = "incorrect-word";
            typedWord.textContent = item.typed;
            const expectedWord = document.createElement("span");
            expectedWord.className = "expected-word";
            expectedWord.textContent = item.expected;
            listItem.append(typedWord, document.createTextNode(" → "), expectedWord);
            correctionList.append(listItem);
        }
        noCorrections.hidden = items.length > 0;
    }

    async function loadResult() {
        try {
            const response = await fetch(`/api/results/${encodeURIComponent(testId)}`);
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Unable to load this test result.");
            }

            document.getElementById("result-wpm").textContent = Number(result.wpm).toFixed(2);
            document.getElementById("result-accuracy").textContent = `${Number(result.accuracy).toFixed(2)}%`;
            document.getElementById("result-correct").textContent = result.correct_chars;
            document.getElementById("result-incorrect").textContent = result.incorrect_chars;
            document.getElementById("result-duration").textContent = `${Number(result.duration).toFixed(2)} seconds`;
            const date = new Date(result.created_at);
            document.getElementById("result-date").textContent = Number.isNaN(date.getTime())
                ? result.created_at
                : date.toLocaleString();
            renderComparison(result.paragraph, result.typed_text);
            renderCorrections(result.incorrect_words);
            details.hidden = false;
            setMessage("Your result was saved successfully.", "success");
        } catch (error) {
            setMessage(error.message || "Unable to load this test result.", "error");
        }
    }

    loadResult();
})();
