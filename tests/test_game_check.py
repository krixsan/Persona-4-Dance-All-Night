from paths import ROOT
import tempfile
import unittest
from pathlib import Path

import game_check
from test_prepare import fixture
from prepare import parse_self


class GameCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.game = Path(self.tmp.name)
        (self.game / 'sce_sys').mkdir()
        (self.game / 'sce_sys' / 'param.sfo').write_bytes(b'not an SFO')
        (self.game / 'eboot.bin').write_bytes(fixture())

    def tearDown(self):
        self.tmp.cleanup()

    def test_accepts_any_readable_executable_without_claiming_compatibility(self):
        self.assertIsNone(game_check.problem(self.game))
        profile = game_check.profile(self.game)
        self.assertEqual(profile['name'], 'generic')
        self.assertEqual(profile['variant'], 'source-only')
        self.assertFalse(profile['patches'])

    def test_prefers_local_decrypted_elf(self):
        elf = parse_self(fixture())[0]
        (self.game / 'eboot.elf').write_bytes(elf)
        (self.game / 'eboot.bin').write_bytes(b'SELF data not available to the loader')
        self.assertEqual(game_check.executable_path(self.game).name, 'eboot.elf')
        self.assertIsNone(game_check.problem(self.game))

    def test_rejects_unreadable_executable(self):
        (self.game / 'eboot.bin').write_bytes(b'not an executable')
        self.assertEqual(game_check.problem(self.game)[0], 'unreadable')

    def test_pkg_tool_layout_needs_flattening(self):
        (self.game / 'Image0').mkdir()
        (self.game / 'Image0' / 'eboot.bin').write_bytes(fixture())
        self.assertEqual(game_check.problem(self.game)[0], 'split_layout')
        self.assertIn('Image0', game_check.explain('split_layout', '?', '?'))


if __name__ == '__main__':
    unittest.main()
