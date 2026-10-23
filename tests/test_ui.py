import os
import uuid

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5001")
WAIT_SECONDS = 10


@pytest.fixture
def browser():
    options = webdriver.ChromeOptions()
    if os.environ.get("HEADLESS", "true").lower() != "false":
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(0)
    driver.get(BASE_URL)
    yield driver
    driver.quit()


def wait_for(driver, condition):
    return WebDriverWait(driver, WAIT_SECONDS).until(condition)


def start_test(driver):
    wait_for(
        driver,
        EC.element_to_be_clickable((By.ID, "start-button")),
    ).click()


def test_home_page_loads_successfully(browser):
    assert browser.title == "Typing Speed Test"
    assert browser.find_element(By.TAG_NAME, "h1").text == "Typing Speed Test"


def test_typing_paragraph_is_displayed(browser):
    paragraph = wait_for(
        browser,
        lambda driver: driver.find_element(By.ID, "passage").text
        if driver.find_element(By.ID, "passage").text != "Loading a fresh passage..."
        else False,
    )
    assert paragraph


def test_start_test_button_works(browser):
    start_test(browser)
    assert browser.find_element(By.ID, "message").text.startswith("The test has started")


def test_countdown_timer_starts_and_decreases(browser):
    start_test(browser)
    wait_for(
        browser,
        lambda driver: driver.find_element(By.ID, "timer").text != "1:00",
    )


def test_typing_area_is_enabled_after_start(browser):
    typing_area = browser.find_element(By.ID, "typing-input")
    assert not typing_area.is_enabled()
    start_test(browser)
    assert typing_area.is_enabled()


def test_incorrect_characters_are_counted(browser):
    start_test(browser)
    browser.find_element(By.ID, "typing-input").send_keys("X")

    assert browser.find_element(By.ID, "correct-count").text == "0"
    assert browser.find_element(By.ID, "incorrect-count").text == "1"


def test_completed_typing_results_are_displayed(browser):
    paragraph = wait_for(
        browser,
        lambda driver: driver.find_element(By.ID, "passage").text
        if driver.find_element(By.ID, "passage").text != "Loading a fresh passage..."
        else False,
    )
    start_test(browser)
    browser.find_element(By.ID, "typing-input").send_keys(paragraph)

    wait_for(browser, lambda driver: "/results/" in driver.current_url)
    wait_for(browser, EC.visibility_of_element_located((By.ID, "result-wpm")))
    assert browser.find_element(By.ID, "result-correct").text == str(len(paragraph))
    assert browser.find_element(By.ID, "result-accuracy").text == "100.00%"


def test_restart_resets_the_application(browser):
    previous_challenge_id = wait_for(
        browser,
        lambda driver: driver.find_element(By.ID, "passage").get_attribute("data-challenge-id")
        if driver.find_element(By.ID, "passage").get_attribute("data-challenge-id")
        else False,
    )
    start_test(browser)
    browser.find_element(By.ID, "typing-input").send_keys("Dev")
    browser.find_element(By.ID, "restart-button").click()

    wait_for(
        browser,
        lambda driver: driver.find_element(By.ID, "start-button").is_enabled(),
    )
    assert browser.find_element(By.ID, "typing-input").get_attribute("value") == ""
    assert not browser.find_element(By.ID, "typing-input").is_enabled()
    assert browser.find_element(By.ID, "timer").text == "1:00"
    assert (
        browser.find_element(By.ID, "passage").get_attribute("data-challenge-id")
        != previous_challenge_id
    )
    assert browser.find_element(By.ID, "correct-count").text == "0"


def test_user_can_finish_before_the_selected_timer_expires(browser):
    start_test(browser)
    browser.find_element(By.ID, "typing-input").send_keys("A few words")
    browser.find_element(By.ID, "finish-button").click()

    wait_for(browser, lambda driver: "/results/" in driver.current_url)
    assert browser.find_element(By.ID, "result-duration").text.endswith(" seconds")


def test_duration_selection_loads_a_matching_fresh_challenge(browser):
    Select(browser.find_element(By.ID, "duration-select")).select_by_value("15")

    wait_for(
        browser,
        lambda driver: driver.find_element(By.ID, "start-button").is_enabled()
        and driver.find_element(By.ID, "timer").text == "15",
    )
    assert browser.find_element(By.ID, "passage").get_attribute("data-challenge-id").startswith("15-")
    start_test(browser)
    assert browser.find_element(By.ID, "timer").text == "15"


def test_hour_duration_uses_hour_timer_format_and_long_passage(browser):
    Select(browser.find_element(By.ID, "duration-select")).select_by_value("3600")

    wait_for(
        browser,
        lambda driver: driver.find_element(By.ID, "start-button").is_enabled()
        and driver.find_element(By.ID, "timer").text == "1:00:00",
    )
    assert len(browser.find_element(By.ID, "passage").text.split()) >= 1800


def test_typing_mistake_shows_red_word_and_expected_spelling(browser):
    paragraph = wait_for(
        browser,
        lambda driver: driver.find_element(By.ID, "passage").text
        if driver.find_element(By.ID, "passage").text != "Loading a fresh passage..."
        else False,
    )
    mistyped = "X" + paragraph[1:]
    start_test(browser)
    browser.find_element(By.ID, "typing-input").send_keys(mistyped)

    wait_for(browser, lambda driver: "/results/" in driver.current_url)
    wait_for(browser, EC.visibility_of_element_located((By.CSS_SELECTOR, ".incorrect-word")))
    assert browser.find_element(By.CSS_SELECTOR, ".incorrect-word").text
    assert (
        browser.find_element(By.CSS_SELECTOR, ".expected-word").text
        == paragraph.split()[0]
    )


def test_completed_result_is_saved_through_the_api(browser):
    paragraph = wait_for(
        browser,
        lambda driver: driver.find_element(By.ID, "passage").text
        if driver.find_element(By.ID, "passage").text != "Loading a fresh passage..."
        else False,
    )
    start_test(browser)
    browser.find_element(By.ID, "typing-input").send_keys(paragraph)

    wait_for(
        browser,
        lambda driver: "/results/" in driver.current_url,
    )
    assert browser.find_element(By.ID, "result-wpm").text


def test_previous_results_are_displayed_from_sqlite(browser):
    paragraph_element = browser.find_element(By.ID, "passage")
    paragraph = wait_for(
        browser,
        lambda driver: driver.find_element(By.ID, "passage").get_attribute("data-challenge-id")
        if driver.find_element(By.ID, "passage").get_attribute("data-challenge-id")
        else False,
    )
    challenge_id = paragraph
    paragraph = paragraph_element.text
    duration = int(browser.find_element(By.ID, "duration-select").get_attribute("value"))
    browser.execute_async_script(
        """
        const done = arguments[arguments.length - 1];
        fetch('/api/results', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                test_id: arguments[0],
                challenge_id: arguments[1],
                typed_text: arguments[2],
                duration: arguments[3]
            })
        }).then(response => done(response.status))
          .catch(() => done(0));
        """,
        str(uuid.uuid4()),
        challenge_id,
        paragraph,
        min(20, duration),
    )
    browser.refresh()

    wait_for(
        browser,
        lambda driver: any(
            "100.00%" in row.text
            for row in driver.find_elements(By.CSS_SELECTOR, "#results-body tr")
        ),
    )


def test_error_message_is_shown_when_result_api_is_unavailable(browser):
    paragraph = wait_for(
        browser,
        lambda driver: driver.find_element(By.ID, "passage").text
        if driver.find_element(By.ID, "passage").text != "Loading a fresh passage..."
        else False,
    )
    browser.execute_script(
        """
        const originalFetch = window.fetch.bind(window);
        window.fetch = (url, options = {}) => {
            if (url === '/api/results' && options.method === 'POST') {
                return Promise.reject(new Error('backend unavailable'));
            }
            return originalFetch(url, options);
        };
        """
    )
    start_test(browser)
    browser.find_element(By.ID, "typing-input").send_keys(paragraph)

    wait_for(
        browser,
        lambda driver: "could not be saved" in driver.find_element(By.ID, "message").text,
    )
    assert "backend unavailable" in browser.find_element(By.ID, "message").text


def test_application_is_accessible_at_configured_container_or_cluster_url(browser):
    assert browser.current_url.rstrip("/") == BASE_URL.rstrip("/")
    assert browser.find_element(By.ID, "start-button").is_displayed()
