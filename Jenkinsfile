def img_build_hook = null

pipeline {
    agent { label 'python' }
    stages {
        stage('Build Image') {
            steps {
                script {
                    openshift.withCluster() {
                        openshift.withProject() {
                            echo "Starting image build for indy-perf-tester in project: ${openshift.project()}"
                            def bc = openshift.selector("bc", "indy-perf-tester")
                            def buildSel = bc.startBuild()
                            buildSel.logs("-f")
                        }
                    }
                }
            }
        }
    }
}
