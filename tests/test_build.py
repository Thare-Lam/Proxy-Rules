import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('build', Path(__file__).parents[1] / 'scripts/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class ConversionTests(unittest.TestCase):
    def test_nested_rules(self):
        source = 'AND,((PROTOCOL,UDP),(DST-PORT,19302-19309),(GEOIP,CN)),DIRECT'
        self.assertEqual(build.convert_expression(source), 'AND,((NETWORK,udp),(DST-PORT,19302-19309),(GEOIP,CN)),DIRECT')

    def test_unknown_matcher_stops_build(self):
        with self.assertRaises(ValueError):
            build.convert_expression('UNSUPPORTED,example.com,DIRECT')

    def test_cycle_stops_build(self):
        with self.assertRaises(ValueError):
            build.groups_for_mihomo(['a = select,b', 'b = select,a'])

    def test_default_and_timeout(self):
        group = build.groups_for_mihomo(['a = select,DIRECT,PROXY,policy-select-name=PROXY,timeout=5'])[1]
        self.assertEqual(group['proxies'], ['PROXY', 'DIRECT'])
        self.assertEqual(group['timeout'], 5000)

    def test_other_region_re2(self):
        groups = build.groups_for_mihomo(['US = url-test,policy-regex-filter=US|美国', 'Other = url-test,policy-regex-filter=^((?!(US|美国)).)*$'])
        self.assertNotIn('filter', groups[-1])
        self.assertIn('US|美国', groups[-1]['exclude-filter'])


if __name__ == '__main__':
    unittest.main()
