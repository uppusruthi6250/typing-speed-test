# Typing Speed Test

A small, beginner-friendly typing practice app built with HTML, CSS, JavaScript, Flask, and SQLite. The same app is used for the Docker, Kubernetes, Jenkins, and Selenium demonstrations in the 12-week lab plan below.

## Architecture

```text
Chrome browser
  ├── HTML/CSS/JavaScript: timer, typing interaction, live character counts
  └── Flask JSON API
        └── SQLite database (data/typing_test.db)
              └── persistent Docker volume / Kubernetes persistent volume claim
```

Flask serves the test page, result-review page, and JSON API. JavaScript manages the live test and submits a completed result. The backend checks the request, calculates the score again, and writes the score and typed text to SQLite using parameterized SQL. After a successful save, the browser opens a dedicated result page with the score, passage comparison, and corrections. The browser does not supply authoritative WPM or accuracy values.

### Project structure

```text
typing-speed-test/
├── app.py                       # Flask app, API validation, and SQLite operations
├── requirements.txt             # Python dependencies
├── templates/
│   ├── index.html               # Typing test and saved result history
│   └── results.html             # Detailed review for a completed test
├── static/
│   ├── style.css                # Responsive styles
│   ├── script.js                # Timer, live counts, and API calls
│   └── results.js               # Score details, passage comparison, and corrections
├── tests/
│   ├── test_api.py              # Flask API tests (pytest)
│   └── test_ui.py               # Browser tests (Selenium + pytest)
├── Dockerfile                   # Production container using Gunicorn
├── docker-compose.yml           # Container and persistent local data volume
├── .dockerignore
├── .gitignore
├── Jenkinsfile                  # CI pipeline
└── k8s/
    ├── deployment.yaml
    ├── persistent-storage.yaml  # PersistentVolumeClaim
    └── service.yaml
```

## Score rules

- Choose a test from 15 seconds through 1 hour: 15 or 30 seconds, then 1, 2, 5, 10, 15, 30, or 45 minutes, or 1 hour. The timer changes to `MM:SS` or `H:MM:SS` for longer tests.
- The passage length scales with the selected duration at about 30 words per minute, so longer tests provide enough text to type.
- A fresh passage is selected whenever a test is restarted; it will not repeat the immediately previous passage for the same time limit.
- Click **Finish Test** at any time to end early; the full passage also ends the test automatically, and the timer ends it when it reaches zero.
- A test ends when its timer expires or the typed text reaches the passage length. This lets the app show mistakes instead of requiring a perfect copy.
- A correct character matches the challenge at the same position. Incorrect characters are typed characters that do not match at that position, including extra characters.
- **WPM** = number of typed characters ÷ 5 ÷ elapsed minutes.
- **Accuracy** = correct typed characters ÷ total typed characters × 100. Accuracy is 0% when nothing was typed.
- Characters not typed are not counted as incorrect. The backend derives these measures from the submitted text and elapsed duration.
- After a test is saved, the app opens a results page showing WPM, accuracy, character counts, elapsed time, and completion date. The expected passage and submitted text are compared character by character; incorrectly typed words are also shown in red with the expected spelling in green. Word comparison ignores capitalization and punctuation and aligns around extra words. This checks spelling against the selected passage; it is not a general-purpose spell checker.
- Each test gets a UUID. SQLite uses it as the result key, so retries cannot create a duplicate result.

The app creates the SQLite table at startup. The local database is `data/typing_test.db`; generated databases are ignored by Git.

## 1. Install software on Windows

Install the following:

1. **Python 3.10 or newer** from [python.org](https://www.python.org/downloads/). During setup, enable **Add Python to PATH**.
2. **Git for Windows** from [git-scm.com](https://git-scm.com/download/win).
3. **Google Chrome** from [google.com/chrome](https://www.google.com/chrome/).
4. **Docker Desktop** for the Docker lab.
5. **Jenkins** (a local installation or a college-provided server) for the CI lab.
6. **kubectl** and either Docker Desktop Kubernetes or Minikube for the Kubernetes lab.

Check Python and Git from PowerShell:

```powershell
py --version
git --version
```

## 2. Create a virtual environment and install dependencies

Run these commands from the project root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, activate just for the current terminal with:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv\Scripts\Activate.ps1
```

## 3. Run locally

With the virtual environment activated:

```powershell
python app.py
```

Open <http://127.0.0.1:5001>. This uses Flask's built-in server for local development only. The local default is port 5001 to avoid colliding with the Week 1 project on port 5000; change it by setting `PORT`. Docker runs the app with Gunicorn instead. To use a different database path, set it before starting the app:

```powershell
$env:DATABASE_PATH = "data\typing_test.db"
python app.py
```

To choose a different local port:

```powershell
$env:PORT = "5002"
python app.py
```

Stop the local server with `Ctrl+C`.

## 4. Test the Flask APIs

The API health endpoint and empty result list can be checked from PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:5001/api/health
Invoke-RestMethod http://127.0.0.1:5001/api/results
```

First get a challenge; durations are expressed in seconds (for example, 1800 is 30 minutes and 3600 is 1 hour). Use its ID when submitting a result. The server checks the passage and calculates the score:

```powershell
$challenge = Invoke-RestMethod "http://127.0.0.1:5001/api/challenge?duration=1800"
$body = @{
    test_id = [guid]::NewGuid().ToString()
    challenge_id = $challenge.challenge_id
    typed_text = $challenge.paragraph
    duration = 10
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5001/api/results `
    -ContentType "application/json" -Body $body
```

Expected response shapes are `{"status":"ok"}` for health, a JSON array for results, and a result object for a successful save (`201 Created`). Invalid input returns `400`; reusing a test UUID returns `409`. Run backend tests with:

```powershell
python -m pytest -q tests/test_api.py
```

## 5. Create a GitHub repository

On GitHub, create a new **empty** repository (do not initialize it with a README, license, or `.gitignore`). Then, from the project root:

```powershell
git init
git branch -M main
git add .
git commit -m "Add typing speed test DevOps lab project"
git remote add origin https://github.com/YOUR-USERNAME/typing-speed-test.git
git push -u origin main
```

Replace the URL with your repository URL. To make a feature branch and publish it:

```powershell
git switch -c feature/my-change
git add .
git commit -m "Describe the change"
git push -u origin feature/my-change
```

`.gitignore` excludes virtual environments, local database files, logs, and temporary files. Do not commit credentials or secret values.

## 6. Configure Jenkins

Use a Jenkins agent with Git, Python 3, and a Linux shell. The pipeline installs dependencies, runs the Flask API tests, and compiles the Python sources. Selenium is an optional separate stage.

1. Create a Jenkins Pipeline job (or Multibranch Pipeline) and connect it to the GitHub repository.
2. Configure repository credentials if the repository is private.
3. Select **Pipeline script from SCM**, choose Git, enter the repository URL/credentials, and set the script path to `Jenkinsfile`.
4. Run **Build Now** and inspect the stage logs.
5. A GitHub webhook can be configured to trigger builds after pushes; manual builds are sufficient for the lab.

The default pipeline does not require Chrome. To run its Selenium stage, configure the agent with Chrome and a compatible ChromeDriver (or working Selenium Manager), then set the build parameter/environment variable `RUN_SELENIUM=true`. The stage starts a temporary Gunicorn app before running the browser tests.

## 7. Build and run with Docker

Start Docker Desktop first. In PowerShell, from the project root:

```powershell
docker build -t typing-speed-test:local .
docker run --name typing-speed-test -p 5000:5000 `
    -v typing-test-data:/app/data typing-speed-test:local
```

Browse to <http://localhost:5000>. In another terminal:

```powershell
docker logs typing-speed-test
docker stop typing-speed-test
docker rm typing-speed-test
```

The Docker named volume stores the SQLite database beyond container removal. Alternatively, Docker Compose builds and starts the same service:

```powershell
docker compose up --build -d
docker compose logs -f
docker compose down
```

`docker compose down` stops/removes the container but keeps the `typing-data` named volume. The image uses Gunicorn with one worker, which is appropriate for this small SQLite demonstration. Remove the saved database only when intended with `docker compose down -v` or `docker volume rm typing-test-data` (for the standalone `docker run` volume).

## 8. Deploy with Kubernetes

Use Docker Desktop Kubernetes or Minikube and make sure `kubectl` is connected to that local cluster. Build the image:

```powershell
docker build -t typing-speed-test:local .
```

For Minikube, load the locally built image into the cluster:

```powershell
minikube image load typing-speed-test:local
```

Apply the persistent volume claim, Deployment, and Service:

```powershell
kubectl apply -f k8s/persistent-storage.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl get pods
kubectl get deployments
kubectl get services
```

The health endpoint is used for both Kubernetes readiness and liveness probes. For reliable local access on any cluster, port-forward the Service:

```powershell
kubectl port-forward service/typing-speed-test 8080:80
```

Open <http://127.0.0.1:8080>. For Minikube, `minikube service typing-speed-test --url` is another way to get a reachable URL.

Delete these lab resources when finished:

```powershell
kubectl delete -f k8s/service.yaml
kubectl delete -f k8s/deployment.yaml
kubectl delete -f k8s/persistent-storage.yaml
```

The claim requests storage from the cluster's default StorageClass; a local Kubernetes installation needs a working storage provisioner. The single replica and `ReadWriteOnce` claim are intentional: SQLite is a local-file database, not a multi-replica shared database. A rescheduled pod must be able to reattach its volume, and deleting the PVC can delete its data depending on the storage provider's reclaim policy. Back up the database before removing storage or moving the workload to another cluster.

## 9. Run Selenium browser tests

Start the app in one PowerShell terminal:

```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```

In a second terminal, activate the environment and run:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q tests/test_ui.py
```

The Selenium tests use Chrome in headless mode by default and explicit waits. Selenium Manager attempts to locate/download a matching driver. If the browser is not at the default address, set `BASE_URL`, for example:

```powershell
$env:BASE_URL = "http://localhost:5001"
python -m pytest -q tests/test_ui.py
```

The UI suite verifies loading, fresh challenges and duration selection, starting, countdown, enabled input, incorrect-character counting, red-word/correct-spelling feedback, completed scores, restart, API persistence, history display, a simulated unavailable save API, and accessibility at the configured container/cluster URL. The final URL check does not itself deploy Docker or Kubernetes; deploy the app first and point `BASE_URL` at that running instance when demonstrating those environments.

## 10. Twelve-week DevOps laboratory plan

| Week | Lab activity | Project use |
|---|---|---|
| 1 | Create the required simple event registration form. | Keep it as the separate Week 1 exercise unless the instructor permits including it here. |
| 2 | Explore Git and GitHub commands. | Practice init, status, add, commit, branch, and push. |
| 3 | Perform source code management on GitHub. | Use the Week 1 event registration form as instructed. |
| 4 | Install Jenkins and explore its environment. | Create a Jenkins job connected to the repository. |
| 5 | Demonstrate continuous integration. | Run the `Jenkinsfile` backend test pipeline. |
| 6 | Explore Docker commands. | Build, inspect, run, log, stop, and remove a container. |
| 7 | Develop and run the containerized app. | Run the Typing Speed Test with persistent host data. |
| 8 | Integrate Docker and Kubernetes. | Build/tag an image and make it available to the local cluster. |
| 9 | Deploy and run the app in Kubernetes. | Apply the manifests, inspect health, and port-forward the Service. |
| 10 | Install and explore Selenium. | Install dependencies and launch Chrome WebDriver. |
| 11 | Write a simple JavaScript program and test it using Selenium. | Use a small instructor-assigned exercise separate from the app. |
| 12 | Write and execute Selenium tests for a containerized app. | Point `BASE_URL` at the Docker or Kubernetes deployment and run `tests/test_ui.py`. |

## Troubleshooting

- **`py` or `python` is not recognized:** reinstall Python with PATH enabled, then open a new PowerShell window.
- **Activation is blocked:** use the process-scoped execution policy shown above, or run `.venv\Scripts\python.exe` directly.
- **Port 5001 is already in use:** choose another local port, for example `$env:PORT = "5002"`, or map Docker to a free host port, such as `-p 5001:5000`.
- **API tests fail with a database error:** ensure the process can write to the configured database directory; local default is `data`.
- **Docker cannot start:** start Docker Desktop and wait until its engine reports ready.
- **Kubernetes pod is pending:** inspect `kubectl describe pod <pod-name>` and `kubectl get pvc`; the local cluster needs available storage provisioning.
- **Kubernetes reports `ImagePullBackOff`:** build/load the image into the active cluster and verify the image name matches `typing-speed-test:local`.
- **Selenium cannot start Chrome:** install/update Chrome, ensure the Jenkins/browser host can run Chrome, and allow Selenium Manager to obtain a compatible driver. Set `HEADLESS=false` only when a desktop session is available.
- **Selenium reports connection refused:** start the app before running the UI suite and verify `BASE_URL`.
- **Results disappear in Docker/Kubernetes:** verify the mounted path is `/app/data`, and do not delete the host `data` directory or the Kubernetes PVC.
