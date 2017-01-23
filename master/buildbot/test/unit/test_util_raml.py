# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from __future__ import absolute_import
from __future__ import print_function

import textwrap

from twisted.trial import unittest

from buildbot.util import raml


class TestRaml(unittest.TestCase):

    def setUp(self):
        self.api = raml.RamlSpec()

    def test_api(self):
        self.assertTrue(self.api.api is not None)

    def test_endpoints(self):
        self.assertIn(
            "/masters/{masterid}/builders/{builderid}/workers/{workerid}",
            self.api.endpoints.keys())

    def test_endpoints_uri_parameters(self):
        # comparaison of OrderedDict do not take in account order :(
        # this is why we compare str repr, to make sure the endpoints are in
        # the right order
        self.assertEqual(str(self.api.endpoints[
            "/masters/{masterid}/builders/{builderid}/workers/{workerid}"]['uriParameters']),
            str(raml.OrderedDict([
                ('masterid', raml.OrderedDict([
                    ('type', 'number'), ('description', 'the id of the master')])),
                ('builderid', raml.OrderedDict([
                    ('type', 'number'), ('description', 'the id of the builder')])),
                ('workerid', raml.OrderedDict([
                    ('type', 'number'), ('description', 'the id of the worker')]))]))
        )

    def test_types(self):
        self.assertIn(
            "log",
            self.api.types.keys())

    def test_json_example(self):
        self.assertEqual(
            textwrap.dedent(
                self.api.format_json(self.api.types["build"]['example'], 0)),
            textwrap.dedent("""
            {
                "builderid": 10,
                "buildid": 100,
                "buildrequestid": 13,
                "workerid": 20,
                "complete": false,
                "complete_at": null,
                "masterid": 824,
                "number": 1,
                "results": null,
                "started_at": 1451001600,
                "state_string": "created",
                "properties": {}
            }""").strip())

    def test_endpoints_by_type(self):
        self.assertIn(
            "/masters/{masterid}/builders/{builderid}/workers/{workerid}",
            self.api.endpoints_by_type['worker'].keys())

    def test_iter_actions(self):
        build = self.api.endpoints_by_type['build']
        actions = dict(self.api.iter_actions(build['/builds/{buildid}']))
        self.assertEqual(sorted(actions.keys()), sorted(['rebuild', 'stop']))

    def test_rawendpoints(self):
        self.assertIn(
            "/steps/{stepid}/logs/{log_slug}/raw",
            self.api.rawendpoints.keys())
