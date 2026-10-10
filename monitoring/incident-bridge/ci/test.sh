#!/bin/sh
set -eu
mkdir -p /reports
python ci/unittest-junit.py test_bridge /reports/junit.xml
