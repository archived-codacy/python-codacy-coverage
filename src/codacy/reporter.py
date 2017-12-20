"""Codacy coverage reporter for Python"""

import argparse
import contextlib
import json
import logging
import os
from xml.dom import minidom

import requests
from requests.packages.urllib3 import util as urllib3_util

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

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
    """Get the git revision hash if it is not set by an env variable: GIT_REVISION_HASH"""
    if os.getenv("GIT_REVISION_HASH"):
        return os.getenv("GIT_REVISION_HASH")

    import subprocess
    return subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode("utf-8").strip()


def get_git_directory():
    """Get the git repo path if it is not set by an env variable: GIT_DIRECTORY"""
    if os.getenv("GIT_DIRECTORY"):
        return os.getenv("GIT_DIRECTORY")

    import subprocess
    return subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).decode("utf-8").strip()


def generate_filename(sources, filename, git_directory):
    def strip_prefix(line, prefix):
        if line.startswith(prefix):
            return line[len(prefix):]
        else:
            return line

    if not git_directory:
        git_directory = get_git_directory()

    for source in sources:
        if os.path.exists(os.path.join(source, filename)):
            return strip_prefix(source, git_directory).strip("/") + "/" + filename.strip("/")

    return filename


def merge_and_round_reports(report_list):
    """Merges together several report structures from parse_report_file (and rounds all values)"""

    if len(report_list) == 1:
        final_report = report_list[0]
    else:
        final_report = {
            'language': "python",
            'fileReports': []
        }

        total_lines = 0
        for report in report_list:
            # First, merge together detailed report structures
            # This assumes no overlap
            # TODO: What should we do if there is a file listed multiple times?
            final_report['fileReports'] += report['fileReports']
            total_lines += report['codeLines']

        # Coverage weighted average (by number of lines of code) of all files
        average_sum = 0
        for file_entry in final_report['fileReports']:
            average_sum += file_entry['total'] * file_entry['codeLines']

        final_report['total'] = average_sum / total_lines
        final_report['codeLines'] = total_lines

    # Round all total values
    for file_entry in final_report['fileReports']:
        file_entry['total'] = int(file_entry['total'])
    final_report['total'] = int(final_report['total'])

    return final_report


def parse_report_file(report_file, git_directory):
    """Parse XML file and POST it to the Codacy API
    :param report_file:
    """

    # Convert decimal string to decimal percent value
    def percent(s):
        return float(s) * 100

    # Parse the XML into the format expected by the API
    report_xml = minidom.parse(report_file)

    report = {
        'language': "python",
        'total': percent(report_xml.getElementsByTagName('coverage')[0].attributes['line-rate'].value),
        'fileReports': [],
    }

    sources = [x.firstChild.nodeValue for x in report_xml.getElementsByTagName('source')]
    classes = report_xml.getElementsByTagName('class')
    total_lines = 0
    for cls in classes:
        lines = cls.getElementsByTagName('line')
        total_lines += len(lines)
        file_report = {
            'filename': generate_filename(sources, cls.attributes['filename'].value, git_directory),
            'total': percent(cls.attributes['line-rate'].value),
            'codeLines': len(lines),
            'coverage': {},
        }
        for line in lines:
            hits = int(line.attributes['hits'].value)
            file_report['coverage'][line.attributes['number'].value] = hits
        report['fileReports'] += [file_report]

    report['codeLines'] = total_lines

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
    parser.add_argument("-r", "--report", help="coverage report file",
                        default=[], type=str,
                        action='append')
    parser.add_argument("-c", "--commit", type=str, help="git commit hash")
    parser.add_argument("-t", "--token", type=str, help="Codacy project token")
    parser.add_argument("-d", "--directory", type=str, help="git top level directory")
    parser.add_argument("-v", "--verbose", help="show debug information", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logging.Logger.setLevel(logging.getLogger(), logging.DEBUG)

    if args.token:
        codacy_project_token = args.token
    else:
        codacy_project_token = os.getenv('CODACY_PROJECT_TOKEN')
        if not codacy_project_token:
            logging.error("environment variable CODACY_PROJECT_TOKEN is not defined.")
            exit(1)

    if not args.commit:
        args.commit = get_git_revision_hash()

    if not args.report:
        args.report.append(DEFAULT_REPORT_FILE)

    # Explictly check ALL files before parsing any
    for rfile in args.report:
        if not os.path.isfile(rfile):
            logging.error("Coverage report " + rfile + " not found.")
            exit(1)

    reports = []
    for rfile in args.report:
        logging.info("Parsing report file %s...", rfile)
        reports.append(parse_report_file(rfile, args.directory))

    report = merge_and_round_reports(reports)

    logging.info("Uploading report...")
    upload_report(report, codacy_project_token, args.commit)
