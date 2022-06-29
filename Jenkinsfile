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
                        echo $(which python3)
                        alias python3=python3.10
                        echo $(which python3)
                        alias pip3=pip3.10
                        scripts/check_python_version.sh 3.10 && scripts/runtests.sh
                        '''
                    }
                }
                stage ('Test Python 3.9') {
                    steps {
                        sh ''' 
                        alias python3=python3.9
                        alias pip3=pip3.9
                        scripts/check_python_version.sh 3.9 && scripts/runtests.sh
                        '''
                    }
                }
                stage ('Test Python 3.8') {
                    steps {
                        sh ''' 
                        alias python3=python3.8
                        alias pip3=pip3.8
                        scripts/check_python_version.sh 3.8 && scripts/runtests.sh
                        '''
                    }
                }
            }
        }
    }
}