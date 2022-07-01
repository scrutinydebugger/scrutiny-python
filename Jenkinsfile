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
                        python3.10 -m venv /tmp/venv3.10
                        scripts/with-venv.sh /tmp/venv3.10 scripts/check-python-version.sh 3.10 && scripts/runtests.sh
                        '''
                    }
                }
                stage ('Test Python 3.9') {
                    steps {
                        sh ''' 
                        python3.9 -m venv /tmp/venv3.10
                        source /tmp/venv3.9/bin/activate

                        scripts/check-python-version.sh 3.9 && scripts/runtests.sh
                        '''
                    }
                }
                stage ('Test Python 3.8') {
                    steps {
                        sh ''' 
                        python3.8 -m venv /tmp/venv3.8
                        source /tmp/venv3.8/bin/activate

                        scripts/check-python-version.sh 3.8 && scripts/runtests.sh
                        '''
                    }
                }
            }
        }
    }
}