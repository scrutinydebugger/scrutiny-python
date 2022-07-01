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
                stage ('Test Python') {
                    parallel(
                        'Python 3.10' : {
                            sh ''' 
                            python3.10 -m venv /tmp/venv3.10
                            scripts/with-venv.sh /tmp/venv3.10 scripts/runtests.sh 3.10
                            '''
                        },
                        'Python 3.9' : {
                            sh ''' 
                            python3.9 -m venv /tmp/venv3.9
                            scripts/with-venv.sh /tmp/venv3.9 scripts/runtests.sh 3.9
                            '''
                        },
                        'Python 3.8': {
                            sh ''' 
                            python3.8 -m venv /tmp/venv3.8
                            scripts/with-venv.sh /tmp/venv3.8 scripts/runtests.sh 3.8
                            '''
                        }
                    )
                }
            }
        }
    }
}