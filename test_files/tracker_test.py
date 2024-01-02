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

import json
import os
import unittest
from unittest import mock

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

    def test_bad_id_resolution(self):
        """Validate that if we encounter a bad id, we handle as expected"""

        self.tst_tracker._httpclient_fallback = False  # Force use of requests

        new_id = "-NEWID"
        good_id = "-GOODID"
        good_idb = "-GOODID_B"
        bad_id = "-BAD"

        tracking.INVALID_IDS.append(bad_id)

        test_cases = [
            # struc of: new_install_id, local_id, parent_id
            {
                "scenario": "Pre-exisitng good install",
                "newid": new_id,
                "localid": good_idb,
                "parentid": good_id,
                "newlocal": good_idb,  # Parent should override
                "newparent": good_id,
                "will_post": False  # Will skip post, local install is good
            },
            {
                "scenario": "Fresh install with valid parent",
                "newid": new_id,
                "localid": None,
                "parentid": good_id,
                "newlocal": good_id,
                "newparent": good_id,
                "will_post": True
            },
            {
                "scenario": "First time install",
                "newid": new_id,
                "localid": None,
                "parentid": None,
                "newlocal": new_id,
                "newparent": new_id,
                "will_post": True
            },
            {
                "scenario": "Bad ID local only",
                "newid": new_id,
                "localid": bad_id,
                "parentid": good_id,
                "newlocal": good_id,
                "newparent": good_id,
                "will_post": True
            },
            {
                "scenario": "Bad ID local and par",
                "newid": new_id,
                "localid": bad_id,
                "parentid": bad_id,
                "newlocal": new_id,
                "newparent": new_id,
                "will_post": True
            },
            {
                "scenario": "Bad ID par",
                "newid": new_id,
                "localid": good_id,
                "parentid": bad_id,
                "newlocal": good_id,
                "newparent": good_id,
                "will_post": False  # Just replace the parent if local ok
            }
        ]

        template_id = """
        {
            "install_date": "2023-10-06 23:12:50.524861",
            "install_id": "$localid",
            "enable_tracking": true,
            "status": null
        }
        """

        template_parid = """
        {
            "IDNAME": "$parentid",
            "date": "2023-10-06 22:43:30.855073"
        }
        """

        def rm_files():
            try:
                os.remove(self.tst_tracker._tracker_json)
            except FileNotFoundError:
                pass
            try:
                os.remove(self.tst_tracker._tracker_idbackup)
            except FileNotFoundError:
                pass

        def do_setup(tcase):
            base = os.path.dirname(__file__)
            self.tst_tracker._tracker_json = os.path.join(
                base, "tst_tracker.json")
            self.tst_tracker._tracker_idbackup = os.path.join(
                base, "tst_tracker_backup.json")

            rm_files()

            if tcase["localid"]:
                with open(self.tst_tracker._tracker_json, 'w') as fd:
                    data = template_id.replace("$localid", tcase["localid"])
                    fd.write(data)

            if tcase["parentid"]:
                with open(self.tst_tracker._tracker_idbackup, 'w') as fd:
                    data = template_parid.replace(
                        "$parentid", tcase["parentid"])
                    fd.write(data)

            self.assertEqual(os.path.isfile(self.tst_tracker._tracker_json),
                             tcase.get("localid") is not None)
            self.assertEqual(os.path.isfile(self.tst_tracker._tracker_idbackup),
                             tcase.get("parentid") is not None)

        def simulate_startup(tcase):
            # Set mock return for requests.
            rawdata = {"name": new_id}

            resp = mock.MagicMock()
            resp.ok = True
            resp.text = json.dumps(rawdata)

            # Test the optin status.
            with mock.patch("MCprep_addon.tracking.requests.post",
                            return_value=resp) as resp_mock:
                self.tst_tracker.set_tracker_json()
                tracking.trackInstalled(background=False)
                if tcase["will_post"] is True:
                    resp_mock.assert_called_once()
                else:
                    resp_mock.assert_not_called()

        def check_outcome(tcase):
            self.assertTrue(os.path.isfile(self.tst_tracker._tracker_json))
            self.assertTrue(os.path.isfile(self.tst_tracker._tracker_idbackup))

            with open(self.tst_tracker._tracker_json, 'r') as fd:
                content = fd.read()
                self.assertIn(tcase["newlocal"], content)
            with open(self.tst_tracker._tracker_idbackup, 'r') as fd:
                content = fd.read()
                self.assertIn(tcase["newparent"], content)

        for tcase in test_cases:
            with self.subTest(tcase["scenario"]):

                do_setup(tcase)
                simulate_startup(tcase)
                check_outcome(tcase)
                rm_files()
        rm_files()
