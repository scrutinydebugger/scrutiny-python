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
                        sh ''' 
                        VENV_DIR=/tmp/venv3.10
                        python3.10 -m venv $VENV_DIR
                        scripts/with-venv.sh $VENV_DIR scripts/check-python-version.sh 3.10
                        scripts/with-venv.sh $VENV_DIR scripts/runtests.sh
                        '''
                    }
                }
                stage ('Test Python 3.9') {
                    steps {
                        sh ''' 
                        VENV_DIR=/tmp/venv3.9
                        python3.9 -m venv $VENV_DIR
                        scripts/with-venv.sh $VENV_DIR scripts/check-python-version.sh 3.9
                        scripts/with-venv.sh $VENV_DIR scripts/runtests.sh
                        '''
                    }
                }
                stage ('Test Python 3.8') {
                    steps {
                        sh ''' 
                        VENV_DIR=/tmp/venv3.8
                        python3.8 -m venv $VENV_DIR
                        scripts/with-venv.sh $VENV_DIR scripts/check-python-version.sh  3.8
                        scripts/with-venv.sh $VENV_DIR scripts/runtests.sh
                        '''
                    }
                }
            }
        }
    }
}