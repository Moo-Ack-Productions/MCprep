# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

from pathlib import Path
import os
import unittest

import bpy

from MCprep_addon import conf


class AddonTest(unittest.TestCase):
    """Create addon level tests, and ensures enabled for later tests."""

    @staticmethod
    def addon_path() -> Path:
        scripts = bpy.utils.user_resource("SCRIPTS")
        return Path(scripts, "addons", "MCprep_addon")

    def test_enable(self):
        """Ensure the addon can be directly enabled."""
        bpy.ops.preferences.addon_enable(module="MCprep_addon")

    def test_disable_enable(self):
        """Ensure we can safely disable and re-enable addon without error."""
        bpy.ops.preferences.addon_disable(module="MCprep_addon")
        bpy.ops.preferences.addon_enable(module="MCprep_addon")

    def test_translations(self):
        """Safely ensures translations are working fine still.

        Something go wrong, blender stuck in another language? Run in console:
        bpy.context.preferences.view.language = "en_US"
        """
        init_lang = bpy.context.preferences.view.language
        try:
            self._test_translation()
        except Exception:
            raise
        finally:
            bpy.context.preferences.view.language = init_lang

    def _test_translation(self):
        """Ensure that creating the MCprep environment is error-free."""
        test_env = conf.MCprepEnv()
        mcprep_dir = self.addon_path()
        lang_folder = mcprep_dir / "MCprep_resources" / "Languages"
        test_env.languages_folder = lang_folder

        # Don't assign translations, to force building the map in memory
        # translations_py = mcprep_dir / "translations.py"
        # test_env.translations = translations_py

        # Force load translations into this instance of MCprepEnv
        test_env._load_translations()

        self.assertIn(
            "en_US", test_env.languages, "Missing default translation key")
        self.assertTrue(
            test_env.use_direct_i18n, "use_direct_i18n should be True")

        # Magic string evaluations, will break if source po's change
        test_translations = [
            ("ru_RU", "Restart blender", "Перезапустите блендер"),
            # Blender 4.0+ only has 'zh_HANS', 'zh_HANT'
            ("zh_HANS" if bpy.app.version > (4, 0) else "zh_CN", "Texture pack folder", "材质包文件夹"),
            ("en_US", "Mob Spawner", "Mob Spawner"),
        ]
        for lang, src, dst in test_translations:
            with self.subTest(lang):
                # First ensure the mo files exist
                self.assertTrue(
                    os.path.isfile(
                        lang_folder / lang / "LC_MESSAGES" / "mcprep.mo"),
                    f"Missing {lang}'s mo file")

                bpy.context.preferences.view.language = lang
                res = test_env._(src)
                self.assertEqual(res, dst, f"Unexpected {lang} translation)")


if __name__ == '__main__':
    unittest.main(exit=False)
