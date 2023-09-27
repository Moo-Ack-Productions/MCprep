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


import os
import unittest

import bpy

from MCprep_addon.spawner import spawn_util


class AssetQaTest(unittest.TestCase):
    """Test runner to validate current."""

    @classmethod
    def setUpClass(cls):
        bpy.ops.preferences.addon_enable(module="MCprep_addon")

    def _qa_helper(self, basepath: str, allow_packed: bool) -> str:
        """File used to help QC an open blend file."""

        # bpy.ops.file.make_paths_relative() instead of this, do manually.
        different_base = []
        not_relative = []
        missing = []
        for img in bpy.data.images:
            if not img.filepath:
                continue
            abspath = os.path.abspath(bpy.path.abspath(img.filepath))
            if not abspath.startswith(basepath):
                if allow_packed is True and img.packed_file:
                    pass
                else:
                    different_base.append(os.path.basename(img.filepath))
            if img.filepath != bpy.path.relpath(img.filepath):
                not_relative.append(os.path.basename(img.filepath))
            if not os.path.isfile(abspath):
                if allow_packed is True and img.packed_file:
                    pass
                else:
                    missing.append(img.name)

        if len(different_base) > 50:
            return "Wrong basepath for image filepath comparison!"
        if different_base:
            return "Found {} images with different basepath from file: {}".format(
                len(different_base), "; ".join(different_base))
        if not_relative:
            return "Found {} non relative img files: {}".format(
                len(not_relative), "; ".join(not_relative))
        if missing:
            return "Found {} img with missing source files: {}".format(
                len(missing), "; ".join(missing))

    def test_qa_meshswap_file(self):
        """Open the meshswap file, assert there are no relative paths"""
        full_path = os.path.join("MCprep_addon", "MCprep_resources")
        basepath = os.path.abspath(full_path)  # relative to git folder
        blendfile = os.path.join(basepath, "mcprep_meshSwap.blend")
        self.assertTrue(
            os.path.isfile(blendfile),
            f"missing tests dir local meshswap file: {blendfile}")

        print("QC'ing:", blendfile)
        bpy.ops.wm.open_mainfile(filepath=blendfile)
        # do NOT save this file!

        resp = self._qa_helper(basepath, allow_packed=False)
        self.assertFalse(bool(resp), f"Failed: {resp}")

        # detect any non canonical material names?? how to exclude?

        # Affirm that no materials have a principled node, should be basic only

    def test_qa_effects(self):
        """Ensures that effects files meet all QA needs"""

        basepath = os.path.join("MCprep_addon", "MCprep_resources", "effects")
        basepath = os.path.abspath(basepath)  # relative to the dev git folder

        bfiles = []
        for child in os.listdir(basepath):
            if bpy.app.version < (3, 0) and child == "geonodes":
                print("Skipping geo nodes validation pre bpy 3.0")
                continue
            fullp = os.path.join(basepath, child)
            if os.path.isfile(fullp) and child.lower().endswith(".blend"):
                bfiles.append(fullp)
            elif not os.path.isdir(fullp):
                continue
            subblends = [
                os.path.join(basepath, child, blend)
                for blend in os.listdir(os.path.join(basepath, child))
                if os.path.isfile(os.path.join(basepath, child, blend))
                and blend.lower().endswith(".blend")
            ]
            bfiles.extend(subblends)

        print("Checking blend files")
        self.assertGreater(len(bfiles), 0, "No files loaded for bfiles")

        for blend in bfiles:
            tname = blend.replace(".blend", "")
            tname = os.path.basename(tname)
            with self.subTest(tname):
                print("QC'ing:", blend)
                self.assertTrue(os.path.isfile(blend), f"Did not exist: {blend}")
                bpy.ops.wm.open_mainfile(filepath=blend)

                resp = self._qa_helper(basepath, allow_packed=True)
                self.assertFalse(resp, f"{resp} {blend}")

    def test_qa_rigs(self):
        """Ensures that all rig files meet all QA needs.

        NOTE: This test is actually surpisingly fast given the number of files
        it needs to check against, but it's possible it can be unstable. Exit
        early to override if needed.
        """
        if bpy.app.version < (2, 81) or bpy.app.version >= (4, 0):
            self.skipTest("Disabled due to consistent crashing")
            return
        basepath = os.path.join("MCprep_addon", "MCprep_resources", "rigs")
        basepath = os.path.abspath(basepath)  # relative to the dev git folder

        bfiles = []
        for child in os.listdir(basepath):
            fullp = os.path.join(basepath, child)
            if os.path.isfile(fullp) and child.lower().endswith(".blend"):
                bfiles.append(fullp)
            elif not os.path.isdir(fullp):
                continue
            subblends = [
                os.path.join(basepath, child, blend)
                for blend in os.listdir(os.path.join(basepath, child))
                if os.path.isfile(os.path.join(basepath, child, blend))
                and blend.lower().endswith(".blend")
            ]
            bfiles.extend(subblends)

        self.assertGreater(len(bfiles), 0, "No files loaded for bfiles")

        for blend in bfiles:
            tname = blend.replace(".blend", "")
            tname = os.path.basename(tname)
            with self.subTest(tname):
                res = spawn_util.check_blend_eligible(blend, bfiles)
                if res is False:
                    print("QC'ing SKIP:", blend)
                    continue
                print("QC'ing:", blend)
                self.assertTrue(os.path.isfile(blend), f"Did not exist: {blend}")
                bpy.ops.wm.open_mainfile(filepath=blend)

                resp = self._qa_helper(basepath, allow_packed=True)
                print(resp)
                self.assertFalse(resp, resp)

    def test_check_blend_eligible(self):
        fake_base = "MyMob - by Person"

        suffix_new = " pre9.0.0"  # Force active blender instance as older
        suffix_old = " pre1.0.0"  # Force active blender instance as newer.

        p_none = fake_base + ".blend"
        p_new = fake_base + suffix_new + ".blend"
        p_old = fake_base + suffix_old + ".blend"
        rando = "rando_name" + suffix_old + ".blend"

        # Check where input file is the "non-versioned" one.

        res = spawn_util.check_blend_eligible(p_none, [p_none, rando])
        self.assertTrue(res, "Should have been true even if rando has suffix")

        res = spawn_util.check_blend_eligible(p_none, [p_none, p_old])
        self.assertTrue(
            res, "Should be true as curr blend eligible and checked latest")

        res = spawn_util.check_blend_eligible(p_none, [p_none, p_new])
        self.assertFalse(
            res,
            "Should be false as curr blend not eligible and checked latest")

        # Now check if input is a versioned file.

        res = spawn_util.check_blend_eligible(p_new, [p_none, p_new])
        self.assertTrue(
            res, "Should have been true since we are below min blender")

        res = spawn_util.check_blend_eligible(p_old, [p_none, p_old])
        self.assertFalse(
            res, "Should have been false since we are above this min blender")

    def test_check_blend_eligible_middle(self):
        # Warden-like example, where we have equiv of pre2.80, pre3.0, and
        # live blender 3.0+ (presuming we want to test a 2.93-like user)
        fake_base = "WardenExample"

        # Assume the "current" version of blender is like 9.1
        # To make test not be flakey, actual version of blender can be anything
        # in range of 2.7.0 upwards to 8.999.
        suffix_old = " pre2.7.0"  # Force active blender instance as older.
        suffix_mid = " pre9.0.0"  # Force active blender instance as older.
        suffix_new = ""  # presume "latest" version

        p_old = fake_base + suffix_old + ".blend"
        p_mid = fake_base + suffix_mid + ".blend"
        p_new = fake_base + suffix_new + ".blend"

        # Test in order
        filelist = [p_old, p_mid, p_new]

        res = spawn_util.check_blend_eligible(p_old, filelist)
        self.assertFalse(res, "Older file should not match (in order)")
        res = spawn_util.check_blend_eligible(p_mid, filelist)
        self.assertTrue(res, "Mid file SHOULD match (in order)")
        res = spawn_util.check_blend_eligible(p_new, filelist)
        self.assertFalse(res, "Newer file should not match (in order)")

        # Test out of order
        filelist = [p_mid, p_new, p_old]

        res = spawn_util.check_blend_eligible(p_old, filelist)
        self.assertFalse(res, "Older file should not match (out of order)")
        res = spawn_util.check_blend_eligible(p_mid, filelist)
        self.assertTrue(res, "Mid file SHOULD match (out of order)")
        res = spawn_util.check_blend_eligible(p_new, filelist)
        self.assertFalse(res, "Newer file should not match (out of order)")

    def test_check_blend_eligible_real(self):
        # This order below matches a user's who was encountering an error
        # (the actual in-memory python list order)
        riglist = [
            "bee - Boxscape.blend",
            "Blaze - Trainguy.blend",
            "Cave Spider - Austin Prescott.blend",
            "creeper - TheDuckCow.blend",
            "drowned - HissingCreeper-thefunnypie2.blend",
            "enderman - Trainguy.blend",
            "Ghast - Trainguy.blend",
            "guardian - Trainguy.blend",
            "hostile - boxscape.blend",
            "illagers - Boxscape.blend",
            "mobs - Rymdnisse.blend",
            "nether hostile - Boxscape.blend",
            "piglin zombified piglin - Boxscape.blend",
            "PolarBear - PixelFrosty.blend",
            "ravager - Boxscape.blend",
            "Shulker - trainguy.blend",
            "Skeleton - Trainguy.blend",
            "stray - thefunnypie2.blend",
            "Warden - DigDanAnimates pre2.80.0.blend",
            "Warden - DigDanAnimates pre3.0.0.blend",
            "Warden - DigDanAnimates.blend",
            "Zombie - Hissing Creeper.blend",
            "Zombie Villager - Hissing Creeper-thefunnypie2.blend"
        ]
        target_list = [
            "Warden - DigDanAnimates pre2.80.0.blend",
            "Warden - DigDanAnimates pre3.0.0.blend",
            "Warden - DigDanAnimates.blend",
        ]

        if bpy.app.version < (2, 80):
            correct = "Warden - DigDanAnimates pre2.80.0.blend"
        elif bpy.app.version < (3, 0):
            correct = "Warden - DigDanAnimates pre3.0.0.blend"
        else:
            correct = "Warden - DigDanAnimates.blend"

        for rig in target_list:
            res = spawn_util.check_blend_eligible(rig, riglist)
            if rig == correct:
                self.assertTrue(res, f"Did not pick {rig} as correct rig")
            else:
                self.assertFalse(
                    res, f"Should have said {correct} was correct - not {rig}")


if __name__ == '__main__':
    unittest.main(exit=False)
