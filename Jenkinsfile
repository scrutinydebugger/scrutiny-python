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
                stage ('Test Python 3.10') {
                    steps {
                        sh 'alias python3=python3.10'
                        sh 'alias pip3=pip3.10'
                        sh '[[ $(python3 --version) = *"3.10"* ]]'
                        sh '[[ $(pip3 --version) == *"3.10"* ]]'
                        sh 'scripts/runtests.sh'
                    }
                }
                stage ('Test Python 3.9') {
                    steps {
                        sh 'alias python3=python3.9'
                        sh 'alias pip3=pip3.9'
                        sh '[[ $(python3 --version) = *"3.9"* ]]'
                        sh '[[ $(pip3 --version) == *"3.9"* ]]'
                        sh 'scripts/runtests.sh'
                    }
                }
                stage ('Test Python 3.8') {
                    steps {
                        sh 'alias python3=python3.8'
                        sh 'alias pip3=pip3.8'
                        sh '[[ $(python3 --version) = *"3.8"* ]]'
                        sh '[[ $(pip3 --version) == *"3.8"* ]]'
                        sh 'scripts/runtests.sh'
                    }
                }
            }
        }
    }
}