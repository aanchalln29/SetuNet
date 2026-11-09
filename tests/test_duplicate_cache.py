"""Unit tests for DuplicateCache flood suppression and storm prevention."""

import time
import unittest

from src.mesh.duplicate_cache import DuplicateCache


class TestDuplicateCache(unittest.TestCase):
    def test_first_observation_is_fresh(self):
        c = DuplicateCache()
        self.assertFalse(c.check_and_mark("MSG-100"))
        self.assertEqual(c.duplicates_suppressed, 0)

    def test_second_observation_is_duplicate(self):
        c = DuplicateCache()
        c.check_and_mark("MSG-100")
        is_dup = c.check_and_mark("MSG-100")
        self.assertTrue(is_dup)
        self.assertEqual(c.duplicates_suppressed, 1)

    def test_ttl_window_expiration(self):
        c = DuplicateCache(window_seconds=1.0)
        c.check_and_mark("MSG-EXP", now=100.0)
        
        # Within window => duplicate
        self.assertTrue(c.check_and_mark("MSG-EXP", now=100.5))
        
        # After window => purged & treated as fresh
        self.assertFalse(c.check_and_mark("MSG-EXP", now=102.0))

    def test_max_entries_lru_eviction(self):
        c = DuplicateCache(max_entries=3)
        c.check_and_mark("M1")
        c.check_and_mark("M2")
        c.check_and_mark("M3")
        c.check_and_mark("M4")  # Evicts M1

        self.assertFalse(c.is_duplicate("M1"))
        self.assertTrue(c.is_duplicate("M2"))
        self.assertTrue(c.is_duplicate("M3"))
        self.assertTrue(c.is_duplicate("M4"))


if __name__ == "__main__":
    unittest.main()
