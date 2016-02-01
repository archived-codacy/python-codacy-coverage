"""Codacy coverage reporter for Python"""

import argparse
import contextlib
import json
import logging
import os
from xml.dom import minidom
from math import floor

import requests
from requests.packages.urllib3 import util as urllib3_util

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

CODACY_PROJECT_TOKEN = os.getenv('CODACY_PROJECT_TOKEN')
CODACY_BASE_API_URL = os.getenv('CODACY_API_BASE_URL', 'https://api.codacy.com')
URL = CODACY_BASE_API_URL + '/2.0/coverage/{commit}/python'
DEFAULT_REPORT_FILE = 'coverage.xml'
MAX_RETRIES = 3
BAD_REQUEST = 400

class _Retry(urllib3_util.Retry):

    def is_forced_retry(self, method, status_code):
        return status_code >= BAD_REQUEST


@contextlib.contextmanager
def _request_session():
    retry = _Retry(total=MAX_RETRIES, raise_on_redirect=False)
    session = requests.Session()
    session.mount("https://", requests.adapters.HTTPAdapter(max_retries=retry))
    with session:
        yield session


def get_git_revision_hash():
    import subprocess

    return subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode("utf-8").strip()


def get_git_directory():
    import subprocess

    return subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).decode("utf-8").strip()


def file_exists(rootdir, filename):
    for root, subFolders, files in os.walk(rootdir):
        if filename in files:
            return True
        else:
            for subFolder in subFolders:
                return file_exists(subFolder, filename)
            return False


def generate_filename(sources, filename):
    def strip_prefix(line, prefix):
        if line.startswith(prefix):
            return line[len(prefix):]
        else:
            return line

    git_directory = get_git_directory()

    for source in sources:
        if file_exists(source, filename):
            return strip_prefix(source, git_directory).strip("/") + "/" + filename.strip("/")

    return filename


def parse_report_file(report_file):
    """Parse XML file and POST it to the Codacy API
    :param report_file:
    """

    # Convert decimal string to floored int percent value
    def percent(s):
        return int(floor(float(s) * 100))

    # Parse the XML into the format expected by the API
    report_xml = minidom.parse(report_file)

    report = {
        'language': "python",
        'total': percent(report_xml.getElementsByTagName('coverage')[0].attributes['line-rate'].value),
        'fileReports': [],
    }

    sources = [x.firstChild.nodeValue for x in report_xml.getElementsByTagName('source')]
    classes = report_xml.getElementsByTagName('class')
    for cls in classes:
        file_report = {
            'filename': generate_filename(sources, cls.attributes['filename'].value),
            'total': percent(cls.attributes['line-rate'].value),
            'coverage': {},
        }
        lines = cls.getElementsByTagName('line')
        for line in lines:
            hits = int(line.attributes['hits'].value)
            if hits >= 1:
                # The API assumes 0 if a line is missing
                file_report['coverage'][line.attributes['number'].value] = hits
        report['fileReports'] += [file_report]

    return report


def upload_report(report, token, commit):
    """Try to send the data, raise an exception if we fail"""
    url = URL.format(commit=commit)
    data = json.dumps(report)
    headers = {
        "project_token": token,
        "Content-Type": "application/json"
    }

    logging.debug(data)

    with _request_session() as session:
        r = session.post(url, data=data, headers=headers, allow_redirects=True)

    logging.debug(r.content)
    r.raise_for_status()

    response = json.loads(r.text)

    try:
        logging.info(response['success'])
    except KeyError:
        logging.error(response['error'])


def run():
    parser = argparse.ArgumentParser(description='Codacy coverage reporter for Python.')
    parser.add_argument("-r", "--report", type=str, help="coverage report file", default=DEFAULT_REPORT_FILE)
    parser.add_argument("-c", "--commit", type=str, help="git commit hash")
    parser.add_argument("-v", "--verbose", help="show debug information", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logging.Logger.setLevel(logging.getLogger(), logging.DEBUG)

    if not CODACY_PROJECT_TOKEN:
        logging.error("environment variable CODACY_PROJECT_TOKEN is not defined.")
        exit(1)

    if not args.commit:
        args.commit = get_git_revision_hash()

    if not os.path.isfile(args.report):
        logging.error("Coverage report " + args.report + " not found.")
        exit(1)

    logging.info("Parsing report file...")
    report = parse_report_file(args.report)

    logging.info("Uploading report...")
    upload_report(report, CODACY_PROJECT_TOKEN, args.commit)
