pipeline {
    agent {
        label 'docker'
    }
    stages {
        stage ('Docker') {
            agent {
                dockerfile {
                    args '-e HOME=/tmp -e BUILD_CONTEXT=ci -e CCACHE_DIR=/ccache -v $HOME/.ccache:/ccache'
                    reuseNode true
                }
            }
            stages {
                stage ('Test Python 3.10') {
                    steps {
                        sh 'alias python3=/usr/local/bin/python3.10'
                        sh 'alias pip3=/usr/local/bin/pip3.10'

                        sh 'scripts/runtests.sh'
                    }
                }
                stage ('Test Python 3.9') {
                    steps {
                        sh 'alias python3=/usr/local/bin/python3.9'
                        sh 'alias pip3=/usr/local/bin/pip3.9'

                        sh 'scripts/runtests.sh'
                    }
                }
                stage ('Test Python 3.8') {
                    steps {
                        sh 'alias python3=/usr/local/bin/python3.8'
                        sh 'alias pip3=/usr/local/bin/pip3.8'
                        sh 'scripts/runtests.sh'
                    }
                }
            }
        }
    }
}