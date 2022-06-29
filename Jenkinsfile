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
                        mkdir -p /tmp/bin/
                        rm -f /tmp/bin/python3
                        rm -f /tmp/bin/pip3
                        ln -s $(which python3.10) /tmp/bin/python3
                        ln -s $(which pip3.10) /tmp/bin/pip3
                        export PATH=/tmp/bin:$PATH

                        scripts/check_python_version.sh 3.10 && scripts/runtests.sh
                        '''
                    }
                }
                stage ('Test Python 3.9') {
                    steps {
                        sh ''' 
                        mkdir -p /tmp/bin/
                        rm -f /tmp/bin/python3
                        rm -f /tmp/bin/pip3
                        ln -s $(which python3.9) /tmp/bin/python3
                        ln -s $(which pip3.9) /tmp/bin/pip3
                        export PATH=/tmp/bin:$PATH

                        scripts/check_python_version.sh 3.9 && scripts/runtests.sh
                        '''
                    }
                }
                stage ('Test Python 3.8') {
                    steps {
                        sh ''' 
                        mkdir -p /tmp/bin/
                        rm -f /tmp/bin/python3
                        rm -f /tmp/bin/pip3
                        ln -s $(which python3.8) /tmp/bin/python3
                        ln -s $(which pip3.8) /tmp/bin/pip3
                        export PATH=/tmp/bin:$PATH

                        scripts/check_python_version.sh 3.8 && scripts/runtests.sh
                        '''
                    }
                }
            }
        }
    }
}