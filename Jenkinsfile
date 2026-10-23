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
                sh 'python3 -m venv .venv'
                sh '.venv/bin/python -m pip install --upgrade pip'
                sh '.venv/bin/python -m pip install -r requirements.txt'
            }
        }

        stage('Backend tests and validation') {
            steps {
                sh '.venv/bin/python -m pytest -q tests/test_api.py'
                sh '.venv/bin/python -m compileall -q app.py tests'
            }
        }

        stage('Selenium browser tests') {
            when {
                environment name: 'RUN_SELENIUM', value: 'true'
            }
            steps {
                sh '''set -eu
                    mkdir -p data
                    DATABASE_PATH="$WORKSPACE/data/jenkins-test.db" .venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 1 app:app > gunicorn.log 2>&1 &
                    server_pid=$!
                    trap 'kill "$server_pid" 2>/dev/null || true' EXIT
                    for attempt in $(seq 1 30); do
                        if curl -fsS http://127.0.0.1:5000/api/health > /dev/null; then
                            break
                        fi
                        sleep 1
                    done
                    BASE_URL=http://127.0.0.1:5000 .venv/bin/python -m pytest -q tests/test_ui.py
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
