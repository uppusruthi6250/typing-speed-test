
pipeline {
    agent any

    options {
        timestamps()
    }

    environment {
        IMAGE_NAME = 'typing-speed-test'
        DEPLOYMENT_NAME = 'typing-speed-test'
        CONTAINER_NAME = 'typing-speed-test'
        SERVICE_NAME = 'typing-speed-test-service'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Validate Project') {
            steps {
                bat 'docker --version'
                bat 'kubectl version --client'
                bat 'python --version'
                bat 'python -m compileall -q app.py'
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    env.FULL_IMAGE = ''
                    withCredentials([
                        usernamePassword(
                            credentialsId: 'dockerhub-creds',
                            usernameVariable: 'DOCKER_USER',
                            passwordVariable: 'DOCKER_TOKEN'
                        )
                    ]) {
                        env.FULL_IMAGE = "${DOCKER_USER}/${IMAGE_NAME}:${BUILD_NUMBER}"
                        bat 'docker build -t %DOCKER_USER%/%IMAGE_NAME%:%BUILD_NUMBER% .'
                    }
                }
            }
        }

        stage('Push Image to Docker Hub') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub-creds',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_TOKEN'
                    )
                ]) {
                    bat '''
                        @echo off
                        echo %DOCKER_TOKEN% | docker login -u %DOCKER_USER% --password-stdin
                        if errorlevel 1 exit /b 1
                        docker push %DOCKER_USER%/%IMAGE_NAME%:%BUILD_NUMBER%
                        if errorlevel 1 exit /b 1
                        docker logout
                    '''
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub-creds',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_TOKEN'
                    )
                ]) {
                    bat '''
                        kubectl apply -f k8s/deployment.yaml
                        if errorlevel 1 exit /b 1
                        kubectl apply -f k8s/service.yaml
                        if errorlevel 1 exit /b 1
                        kubectl set image deployment/%DEPLOYMENT_NAME% %CONTAINER_NAME%=%DOCKER_USER%/%IMAGE_NAME%:%BUILD_NUMBER%
                        if errorlevel 1 exit /b 1
                        kubectl rollout status deployment/%DEPLOYMENT_NAME% --timeout=180s
                        if errorlevel 1 exit /b 1
                    '''
                }
            }
        }

        stage('Verify Kubernetes Service') {
            steps {
                bat 'kubectl get deployments'
                bat 'kubectl get pods'
                bat 'kubectl get services'
            }
        }
    }

    post {
        success {
            echo 'CI/CD completed: Docker image pushed and application deployed to Kubernetes.'
        }
        failure {
            echo 'CI/CD failed. Check the console output for the failed stage.'
        }
    }
}
