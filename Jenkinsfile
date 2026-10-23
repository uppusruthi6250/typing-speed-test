
pipeline {
    agent any

    options {
        timestamps()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install Python dependencies') {
            steps {
                bat 'python --version'
                bat 'python -m venv .venv'
                bat '.venv\\Scripts\\python.exe -m pip install --upgrade pip'
                bat '.venv\\Scripts\\python.exe -m pip install -r requirements.txt'
            }
        }

        stage('Backend tests and validation') {
            steps {
                bat '.venv\\Scripts\\python.exe -m pytest -q tests/test_api.py'
                bat '.venv\\Scripts\\python.exe -m compileall -q app.py tests'
            }
        }

        stage('Selenium browser tests') {
            when {
                environment name: 'RUN_SELENIUM', value: 'true'
            }
            steps {
                bat '''
                    if not exist data mkdir data
                    set "DATABASE_PATH=%WORKSPACE%\\data\\jenkins-test.db"
                    start "TypingSpeedTestServer" /B .venv\\Scripts\\gunicorn.exe --bind 127.0.0.1:5000 --workers 1 app:app > gunicorn.log 2>&1
                    .venv\\Scripts\\python.exe -c "import time, urllib.request; url='http://127.0.0.1:5000/api/health'; exec('for attempt in range(30):\\n try:\\n  urllib.request.urlopen(url, timeout=2).read(); break\\n except Exception:\\n  time.sleep(1)\\nelse:\\n raise SystemExit(\\'Server did not start; check gunicorn.log\\')')"
                    set "BASE_URL=http://127.0.0.1:5000"
                    .venv\\Scripts\\python.exe -m pytest -q tests/test_ui.py
                '''
            }
        }
    }

    post {
        success {
            echo 'CI pipeline completed successfully.'
        }
        failure {
            echo 'CI pipeline failed. Review the stage logs for details.'
        }
    }
}
