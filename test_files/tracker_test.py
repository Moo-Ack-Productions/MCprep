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

from MCprep_addon import tracking


class TrackingTest(unittest.TestCase):
    """Tracking-related tests."""

    @classmethod
    def setUpClass(cls):
        bpy.ops.preferences.addon_enable(module="MCprep_addon")

    def setUp(self):
        """Clears scene and data between each test"""
        self.tst_tracker = tracking.Singleton_tracking()
        self.tst_tracker.initialize(
            appurl="https://mcprep-1aa04.firebaseio.com/",
            version=str((0, 0, 1)),
            language="en_US",
            blender_version=(2, 80, 0))

        # Setup vars for testing purposes
        self.tst_tracker.dev = True
        self.tst_tracker.tracking_enabled = True
        self.tst_tracker.background = False  # Syncrhonous
        self.tst_tracker.failsafe = False  # test either way

        self._backup_tracker = tracking.Tracker
        tracking.Tracker = self.tst_tracker

    def tearDown(self):
        tracking.Tracker = self._backup_tracker

    def test_track_install_integration(self):
        """Ensure there are no exceptions during install."""
        tracking.trackInstalled(background=False)

    def test_track_usage_integration(self):
        """Ensure there are no exceptions during install."""
        tracking.trackUsage(
            "test_function", param=None, exporter=None, background=False)

    def test_log_error_integration(self):
        """Ensure there are no exceptions log error install."""
        report = {"error": "test_error", "user_comment": "test comment"}
        tracking.logError(report, background=False)

    def test_report_error_wrapper_pass(self):

        @tracking.report_error
        def my_func(_self, context):
            ret_val = context
            return {ret_val}

        with self.subTest("finished"):
            res = my_func(None, context='FINISHED')
            self.assertEqual(res, {'FINISHED'})
        with self.subTest("cancelled"):
            res = my_func(None, context='CANCELLED')
            self.assertEqual(res, {'CANCELLED'})

    def test_report_error_wrapper_exception(self):

        @tracking.report_error
        def my_func(_self, context):
            raise Exception("Test exception")
            return {'FINISHED'}

        # RuntimeError comes from re-raising if bpy.app.background
        # (and trying to mock.patch this object seems to break things)
        with self.assertRaises(RuntimeError):
            res = my_func(None, None)
            self.assertEqual(res, {'CANCELLED'})
