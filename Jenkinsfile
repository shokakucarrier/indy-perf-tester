def img_build_hook = null

pipeline {
    agent { label 'python' }
    stages {
        // stage('preamble') {
        //     steps {
        //         script {
        //             openshift.withCluster() {
        //                 openshift.withProject() {
        //                     echo "Using project: ${openshift.project()}"
                            
        //                     def builds = openshift.selector("bc", "indy-perf-tester").related('builds')
        //                     echo "Found ${builds.count()} builds"
        //                     builds.withEach{
        //                         echo "Got build: ${it.name()}"
        //                     }
        //                 }
        //             }
        //         }
        //     }
        // }
        stage('Build Image') {
            steps {
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
