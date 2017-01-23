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

import json

from twisted.trial import unittest

from buildbot.clients import tryclient


class createJobfile(unittest.TestCase):

    def makeNetstring(self, *strings):
        return ''.join(['%d:%s,' % (len(s), s) for s in strings])

    # version 1 is deprecated and not produced by the try client

    def test_createJobfile_v2_one_builder(self):
        jobid = '123-456'
        branch = 'branch'
        baserev = 'baserev'
        patch_level = 0
        patch_body = 'diff...'
        repository = 'repo'
        project = 'proj'
        who = None
        comment = None
        builderNames = ['runtests']
        properties = {}
        job = tryclient.createJobfile(
            jobid, branch, baserev, patch_level, patch_body, repository,
            project, who, comment, builderNames, properties)
        jobstr = self.makeNetstring(
            '2', jobid, branch, baserev, str(patch_level), patch_body,
            repository, project, builderNames[0])
        self.assertEqual(job, jobstr)

    def test_createJobfile_v2_two_builders(self):
        jobid = '123-456'
        branch = 'branch'
        baserev = 'baserev'
        patch_level = 0
        patch_body = 'diff...'
        repository = 'repo'
        project = 'proj'
        who = None
        comment = None
        builderNames = ['runtests', 'moretests']
        properties = {}
        job = tryclient.createJobfile(
            jobid, branch, baserev, patch_level, patch_body, repository,
            project, who, comment, builderNames, properties)
        jobstr = self.makeNetstring(
            '2', jobid, branch, baserev, str(patch_level), patch_body,
            repository, project, builderNames[0], builderNames[1])
        self.assertEqual(job, jobstr)

    def test_createJobfile_v3(self):
        jobid = '123-456'
        branch = 'branch'
        baserev = 'baserev'
        patch_level = 0
        patch_body = 'diff...'
        repository = 'repo'
        project = 'proj'
        who = 'someuser'
        comment = None
        builderNames = ['runtests']
        properties = {}
        job = tryclient.createJobfile(
            jobid, branch, baserev, patch_level, patch_body, repository,
            project, who, comment, builderNames, properties)
        jobstr = self.makeNetstring(
            '3', jobid, branch, baserev, str(patch_level), patch_body,
            repository, project, who, builderNames[0])
        self.assertEqual(job, jobstr)

    def test_createJobfile_v4(self):
        jobid = '123-456'
        branch = 'branch'
        baserev = 'baserev'
        patch_level = 0
        patch_body = 'diff...'
        repository = 'repo'
        project = 'proj'
        who = 'someuser'
        comment = 'insightful comment'
        builderNames = ['runtests']
        properties = {}
        job = tryclient.createJobfile(
            jobid, branch, baserev, patch_level, patch_body, repository,
            project, who, comment, builderNames, properties)
        jobstr = self.makeNetstring(
            '4', jobid, branch, baserev, str(patch_level), patch_body,
            repository, project, who, comment, builderNames[0])
        self.assertEqual(job, jobstr)

    def test_createJobfile_v5(self):
        jobid = '123-456'
        branch = 'branch'
        baserev = 'baserev'
        patch_level = 0
        patch_body = 'diff...'
        repository = 'repo'
        project = 'proj'
        who = 'someuser'
        comment = 'insightful comment'
        builderNames = ['runtests']
        properties = {'foo': 'bar'}
        job = tryclient.createJobfile(
            jobid, branch, baserev, patch_level, patch_body, repository,
            project, who, comment, builderNames, properties)
        jobstr = self.makeNetstring(
            '5',
            json.dumps({
                'jobid': jobid, 'branch': branch, 'baserev': baserev,
                'patch_level': patch_level, 'patch_body': patch_body,
                'repository': repository, 'project': project, 'who': who,
                'comment': comment, 'builderNames': builderNames,
                'properties': properties,
            }))
        self.assertEqual(job, jobstr)
