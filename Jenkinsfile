pipeline {
    agent {
        label 'docker'
    }
    stages {
        stage ('Docker') {
            agent {
                dockerfile {
                    args '-e HOME=/tmp -e BUILD_CONTEXT=ci'
                    reuseNode true
                }
            }
            stages {
                stage('Testing'){
                    parallel{
                        stage ('Python 3.12') {
                            steps {
                                sh '''
                                python3.12 -m venv venv-3.12
                                SCRUTINY_VENV_DIR=venv-3.12 scripts/with-venv.sh scripts/check-python-version.sh 3.12
                                SCRUTINY_VENV_DIR=venv-3.12 scripts/with-venv.sh scripts/runtests.sh
                                '''
                            }
                        }
                        stage ('Python 3.11') {
                            steps {
                                sh '''
                                python3.11 -m venv venv-3.11
                                SCRUTINY_VENV_DIR=venv-3.11 scripts/with-venv.sh scripts/check-python-version.sh 3.11
                                SCRUTINY_VENV_DIR=venv-3.11 scripts/with-venv.sh scripts/runtests.sh
                                '''
                            }
                        }
                        stage ('Python 3.10') {
                            steps {
                                sh '''
                                python3.10 -m venv venv-3.10
                                SCRUTINY_VENV_DIR=venv-3.10 scripts/with-venv.sh scripts/check-python-version.sh 3.10
                                SCRUTINY_VENV_DIR=venv-3.10 scripts/with-venv.sh scripts/runtests.sh
                                '''
                            }
                        }
                        stage ('Python 3.9') {
                            steps {
                                sh '''
                                python3.9 -m venv venv-3.9
                                SCRUTINY_VENV_DIR=venv-3.9 scripts/with-venv.sh scripts/check-python-version.sh 3.9
                                SCRUTINY_VENV_DIR=venv-3.9 scripts/with-venv.sh scripts/runtests.sh
                                '''
                            }
                        }
                        stage ('Python 3.8') {
                            steps {
                                sh '''
                                python3.8 -m venv venv-3.8
                                SCRUTINY_VENV_DIR=venv-3.8 scripts/with-venv.sh scripts/check-python-version.sh 3.8
                                SCRUTINY_VENV_DIR=venv-3.8 scripts/with-venv.sh scripts/runtests.sh
                                '''
                            }
                        }
                    }
                }
            }
        }
    }
}
