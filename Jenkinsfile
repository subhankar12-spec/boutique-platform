pipeline {
    agent { label 'isolated-builder' }
    options { timestamps(); timeout(time: 30, unit: 'MINUTES'); disableConcurrentBuilds() }
    stages {
        stage('Source secret scan') {
            steps { sh 'trivy fs --scanners secret --exit-code 1 --severity HIGH,CRITICAL .' }
        }
        stage('Validate monitoring configuration') {
            steps {
                sh '''set -eu
                    OBS="$WORKSPACE/monitoring"
                    PROM=prom/prometheus@sha256:efd719c99d83b060d9daefdcf00360461adf279f45ef5391f8d111892118753e
                    AM=prom/alertmanager@sha256:e9733bafb1bdef9b00e25a21f8f99dc26a22224bf16641ad754d1649f4c3357a
                    ALLOY=grafana/alloy@sha256:2aa2099af76c0098d4af7a4d6e48f86cb66dc1a000222ad927a1c67c6542d13f
                    docker run --rm -v "$OBS:/config:ro" -w /config --entrypoint /bin/promtool "$PROM" test rules rules.test.yml
                    for profile in local homelab nonprod production; do
                      docker run --rm -v "$OBS:/etc/prometheus:ro" --entrypoint /bin/promtool "$PROM" check config --syntax-only "/etc/prometheus/prometheus-$profile.yml"
                    done
                    docker run --rm -v "$OBS/alertmanager.yml:/config.yml:ro" --entrypoint /bin/amtool "$AM" check-config /config.yml
                    for profile in local kubernetes; do
                      docker run --rm -v "$OBS/alloy-$profile.alloy:/config.alloy:ro" "$ALLOY" validate /config.alloy
                    done
                '''
            }
        }
        stage('Test and scan incident bridge') {
            steps {
                sh '''set -eu
                    docker build --pull -t "boutique-incident-bridge:ci-$BUILD_NUMBER" monitoring/incident-bridge
                    trivy image --ignorefile .trivyignore.yaml --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed --format json --output image-scan.json "boutique-incident-bridge:ci-$BUILD_NUMBER"
                    syft "boutique-incident-bridge:ci-$BUILD_NUMBER" -o cyclonedx-json=sbom.json
                '''
            }
        }
    }
    post { always { archiveArtifacts artifacts: 'image-scan.json,sbom.json', allowEmptyArchive: true } }
}
