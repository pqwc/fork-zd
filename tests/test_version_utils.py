import unittest

from src.shared.lib.version_utils import compare_versions, is_version_newer


class VersionUtilsTests(unittest.TestCase):
    def test_equal_versions(self):
        self.assertEqual(compare_versions('1.6.4', '1.6.4'), 0)
        self.assertFalse(is_version_newer('1.6.4', '1.6.4'))

    def test_numeric_newer(self):
        self.assertTrue(is_version_newer('1.7.0', '1.6.4'))
        self.assertFalse(is_version_newer('1.6.4', '1.7.0'))

    def test_suffix_versions(self):
        self.assertTrue(is_version_newer('1.9.8', '1.9.7b'))
        self.assertFalse(is_version_newer('1.9.7b', '1.9.7b'))

    def test_v_prefix(self):
        self.assertEqual(compare_versions('v1.6.4', '1.6.4'), 0)


if __name__ == '__main__':
    unittest.main()
