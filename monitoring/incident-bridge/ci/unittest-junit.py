#!/usr/bin/env python3
"""Run the optional adapter's stdlib tests and emit Jenkins-compatible JUnit."""
import sys
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


class ReportResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.suite = ET.Element('testsuite', name='Incident adapter')
        self.current = None

    def startTest(self, test):
        super().startTest(test)
        self.started = time.monotonic()
        self.current = ET.SubElement(self.suite, 'testcase', name=test.id(),
                                     classname=type(test).__name__)

    def stopTest(self, test):
        self.current.set('time', str(time.monotonic() - self.started))
        super().stopTest(test)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        ET.SubElement(self.current, 'failure').text = self._exc_info_to_string(err, test)

    def addError(self, test, err):
        super().addError(test, err)
        ET.SubElement(self.current, 'error').text = self._exc_info_to_string(err, test)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        ET.SubElement(self.current, 'skipped', message=reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        ET.SubElement(self.current, 'skipped', message='Expected failure')

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        ET.SubElement(self.current, 'failure', message='Unexpected success')

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err:
            kind = 'failure' if issubclass(err[0], test.failureException) else 'error'
            ET.SubElement(self.current, kind, message=str(subtest)).text = self._exc_info_to_string(err, test)


def main():
    # Python adds ci/ rather than the working directory when executing this file.
    sys.path.insert(0, str(Path.cwd()))
    suite = unittest.defaultTestLoader.loadTestsFromName(sys.argv[1])
    result = unittest.TextTestRunner(verbosity=2, resultclass=ReportResult).run(suite)
    cases = list(result.suite)
    result.suite.set('tests', str(len(cases)))
    for name in ('failure', 'error', 'skipped'):
        result.suite.set({'failure': 'failures', 'error': 'errors', 'skipped': 'skipped'}[name],
                         str(sum(case.find(name) is not None for case in cases)))
    ET.ElementTree(result.suite).write(sys.argv[2], encoding='utf-8', xml_declaration=True)
    return 0 if result.testsRun and result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
