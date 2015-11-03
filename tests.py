import unittest
import codacy.reporter
import json


class ReporterTests(unittest.TestCase):
    def compare_parse_result(self, generated_filename, expected_filename):
        def file_get_contents(filename):
            with open(filename) as f:
                return f.read()

        generated = codacy.reporter.parse_report_file(generated_filename)

        json_content = file_get_contents(expected_filename)
        expected = json.loads(json_content)

        self.assertEqual(generated, expected)

    def test_parser_coverage3(self):
        self.maxDiff = None

        self.compare_parse_result('tests/coverage3/cobertura.xml', 'tests/coverage3/coverage.json')

    def test_parser_coverage4(self):
        self.maxDiff = None

        self.compare_parse_result('tests/coverage4/cobertura.xml', 'tests/coverage4/coverage.json')

    def test_parser_git_filepath(self):
        self.maxDiff = None

        self.compare_parse_result('tests/filepath/cobertura.xml', 'tests/filepath/coverage.json')


if __name__ == '__main__':
    unittest.main()
