def ocp_map = '/mnt/ocp/jenkins-openshift-mappings.json'
def bc_section = 'build-configs'

def my_bc = null

pipeline {
    agent { label 'python' }
    stages {
        stage('Load OCP Mappings') {
            steps {
                echo "Load OCP Mapping document"
                script {
                    if (fileExists ocp_map){
                        def jsonObj = readJSON file: ocp_map
                        if (bc_section in jsonObj){
                            if (env.GIT_URL in jsonObj[bc_section]) {
                                echo "Found BC for Git repo: ${env.GIT_URL}"
                                if (env.BRANCH_NAME in jsonObj[bc_section][env.GIT_URL]) {
                                    img_build_hook = jsonObj[bc_section][env.GIT_URL][env.BRANCH_NAME]
                                } else {
                                    img_build_hook = jsonObj[bc_section][env.GIT_URL]['default']
                                }
                            }
                        }
                    }
                }
            }
        }
        stage('Build Image') {
            steps {
                script {
                    openshift.withCluster() {
                        openshift.withProject() {
                            echo "Starting image build for indy-perf-tester in project: ${openshift.project()}"
                            def bc = openshift.selector("bc", my_bc)
                            def buildSel = bc.startBuild()
                            buildSel.logs("-f")
                        }
                    }
                }
            }
        }
    }
}
