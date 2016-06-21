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
import os
import shutil
import sys

import mock

import twisted
from twisted.internet import defer
from twisted.protocols import basic
from twisted.python.compat import NativeStringIO
from twisted.trial import unittest

from buildbot.schedulers import trysched
from buildbot.test.util import dirs
from buildbot.test.util import scheduler


class TryBase(scheduler.SchedulerMixin, unittest.TestCase):
    OBJECTID = 26
    SCHEDULERID = 6

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    def makeScheduler(self, **kwargs):
        sched = self.attachScheduler(trysched.Try_Userpass(**kwargs),
                                     self.OBJECTID, self.SCHEDULERID)
        # Try will return a remote version of master.status, so give it
        # something to return
        sched.master.status = mock.Mock()
        return sched

    def test_filterBuilderList_ok(self):
        sched = trysched.TryBase(
            name='tsched', builderNames=['a', 'b', 'c'], properties={})
        self.assertEqual(sched.filterBuilderList(['b', 'c']), ['b', 'c'])

    def test_filterBuilderList_bad(self):
        sched = trysched.TryBase(
            name='tsched', builderNames=['a', 'b'], properties={})
        self.assertEqual(sched.filterBuilderList(['b', 'c']), [])

    def test_filterBuilderList_empty(self):
        sched = trysched.TryBase(
            name='tsched', builderNames=['a', 'b'], properties={})
        self.assertEqual(sched.filterBuilderList([]), ['a', 'b'])

    @defer.inlineCallbacks
    def test_enabled_callback(self):
        sched = self.makeScheduler(name='tsched', builderNames=['a'],
                                   port='tcp:9999', userpass=[('fred', 'derf')])
        expectedValue = not sched.enabled
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, expectedValue)
        expectedValue = not sched.enabled
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, expectedValue)

    @defer.inlineCallbacks
    def test_disabled_activate(self):
        sched = self.makeScheduler(name='tsched', builderNames=['a'],
                                   port='tcp:9999', userpass=[('fred', 'derf')])
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, False)
        r = yield sched.activate()
        self.assertEqual(r, None)

    @defer.inlineCallbacks
    def test_disabled_deactivate(self):
        sched = self.makeScheduler(name='tsched', builderNames=['a'],
                                   port='tcp:9999', userpass=[('fred', 'derf')])
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, False)
        r = yield sched.deactivate()
        self.assertEqual(r, None)


class JobdirService(dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        self.jobdir = 'jobdir'
        self.newdir = os.path.join(self.jobdir, 'new')
        self.curdir = os.path.join(self.jobdir, 'cur')
        self.tmpdir = os.path.join(self.jobdir, 'tmp')
        self.setUpDirs(self.jobdir, self.newdir, self.curdir, self.tmpdir)

    def tearDown(self):
        self.tearDownDirs()

    def test_messageReceived(self):
        # stub out svc.scheduler.handleJobFile and .jobdir
        scheduler = mock.Mock()

        def handleJobFile(filename, f):
            self.assertEqual(filename, 'jobdata')
            self.assertEqual(f.read(), 'JOBDATA')
        scheduler.handleJobFile = handleJobFile
        scheduler.jobdir = self.jobdir

        svc = trysched.JobdirService(scheduler=scheduler, basedir=self.jobdir)

        # create some new data to process
        jobdata = os.path.join(self.newdir, 'jobdata')
        with open(jobdata, "w") as f:
            f.write('JOBDATA')

        # run it
        svc.messageReceived('jobdata')


class Try_Jobdir(scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 23
    SCHEDULERID = 3

    def setUp(self):
        self.setUpScheduler()
        self.jobdir = None

    def tearDown(self):
        self.tearDownScheduler()
        if self.jobdir:
            shutil.rmtree(self.jobdir)

    # tests

    def setup_test_startService(self, jobdir, exp_jobdir):
        # set up jobdir
        self.jobdir = os.path.abspath('jobdir')
        if os.path.exists(self.jobdir):
            shutil.rmtree(self.jobdir)
        os.mkdir(self.jobdir)

        # build scheduler
        kwargs = dict(name="tsched", builderNames=['a'], jobdir=self.jobdir)
        sched = self.attachScheduler(
            trysched.Try_Jobdir(**kwargs), self.OBJECTID, self.SCHEDULERID,
            overrideBuildsetMethods=True)

        # watch interaction with the watcher service
        sched.watcher.startService = mock.Mock()
        sched.watcher.stopService = mock.Mock()

    @defer.inlineCallbacks
    def do_test_startService(self):
        # start it
        yield self.sched.startService()

        # check that it has set the basedir correctly
        self.assertEqual(self.sched.watcher.basedir, self.jobdir)
        self.assertEqual(1, self.sched.watcher.startService.call_count)
        self.assertEqual(0, self.sched.watcher.stopService.call_count)

        yield self.sched.stopService()

        self.assertEqual(1, self.sched.watcher.startService.call_count)
        self.assertEqual(1, self.sched.watcher.stopService.call_count)

    def test_startService_reldir(self):
        self.setup_test_startService(
            'jobdir',
            os.path.abspath('basedir/jobdir'))
        return self.do_test_startService()

    def test_startService_reldir_subdir(self):
        self.setup_test_startService(
            'jobdir',
            os.path.abspath('basedir/jobdir/cur'))
        return self.do_test_startService()

    def test_startService_absdir(self):
        self.setup_test_startService(
            os.path.abspath('jobdir'),
            os.path.abspath('jobdir'))
        return self.do_test_startService()

    @defer.inlineCallbacks
    def do_test_startService_but_not_active(self, jobdir, exp_jobdir):
        """Same as do_test_startService, but the master wont activate this service"""
        self.setup_test_startService(
            'jobdir',
            os.path.abspath('basedir/jobdir'))

        self.setSchedulerToMaster(self.OTHER_MASTER_ID)

        # start it
        self.sched.startService()

        # check that it has set the basedir correctly, even if it doesn't start
        self.assertEqual(self.sched.watcher.basedir, self.jobdir)

        yield self.sched.stopService()

        self.assertEqual(0, self.sched.watcher.startService.call_count)
        self.assertEqual(0, self.sched.watcher.stopService.call_count)

    # parseJob

    def test_parseJob_empty(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['a'], jobdir='foo')
        self.assertRaises(
            trysched.BadJobfile, sched.parseJob, NativeStringIO(''))

    def test_parseJob_longer_than_netstring_MAXLENGTH(self):
        self.patch(basic.NetstringReceiver, 'MAX_LENGTH', 100)
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['a'], jobdir='foo')
        jobstr = self.makeNetstring(
            '1', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'buildera', 'builderc'
        )
        jobstr += 'x' * 200

        test_temp_file = NativeStringIO(jobstr)

        self.assertRaises(trysched.BadJobfile,
                          lambda: sched.parseJob(test_temp_file))

    def test_parseJob_invalid(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['a'], jobdir='foo')
        self.assertRaises(
            trysched.BadJobfile, sched.parseJob,
            NativeStringIO('this is not a netstring'))

    def test_parseJob_invalid_version(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['a'], jobdir='foo')
        self.assertRaises(
            trysched.BadJobfile, sched.parseJob, NativeStringIO('1:9,'))

    def makeNetstring(self, *strings):
        return ''.join(['%d:%s,' % (len(s), s) for s in strings])

    def test_parseJob_v1(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '1', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'buildera', 'builderc'
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob, {
            'baserev': '1234',
            'branch': 'trunk',
            'builderNames': ['buildera', 'builderc'],
            'jobid': 'extid',
            'patch_body': 'this is my diff, -- ++, etc.',
            'patch_level': 1,
            'project': '',
            'who': '',
            'comment': '',
            'repository': '',
            'properties': {},
        })

    def test_parseJob_v1_empty_branch_rev(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            # blank branch, rev are turned to None
            '1', 'extid', '', '', '1', 'this is my diff, -- ++, etc.',
            'buildera', 'builderc'
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob['branch'], None)
        self.assertEqual(parsedjob['baserev'], None)

    def test_parseJob_v1_no_builders(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '1', 'extid', '', '', '1', 'this is my diff, -- ++, etc.'
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob['builderNames'], [])

    def test_parseJob_v1_no_properties(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '1', 'extid', '', '', '1', 'this is my diff, -- ++, etc.'
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob['properties'], {})

    def test_parseJob_v2(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '2', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj',
            'buildera', 'builderc'
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob, {
            'baserev': '1234',
            'branch': 'trunk',
            'builderNames': ['buildera', 'builderc'],
            'jobid': 'extid',
            'patch_body': 'this is my diff, -- ++, etc.',
            'patch_level': 1,
            'project': 'proj',
            'who': '',
            'comment': '',
            'repository': 'repo',
            'properties': {},
        })

    def test_parseJob_v2_empty_branch_rev(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            # blank branch, rev are turned to None
            '2', 'extid', '', '', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj',
            'buildera', 'builderc'
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob['branch'], None)
        self.assertEqual(parsedjob['baserev'], None)

    def test_parseJob_v2_no_builders(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '2', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj',
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob['builderNames'], [])

    def test_parseJob_v2_no_properties(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '2', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj',
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob['properties'], {})

    def test_parseJob_v3(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '3', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj', 'who',
            'buildera', 'builderc'
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob, {
            'baserev': '1234',
            'branch': 'trunk',
            'builderNames': ['buildera', 'builderc'],
            'jobid': 'extid',
            'patch_body': 'this is my diff, -- ++, etc.',
            'patch_level': 1,
            'project': 'proj',
            'who': 'who',
            'comment': '',
            'repository': 'repo',
            'properties': {},
        })

    def test_parseJob_v3_empty_branch_rev(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            # blank branch, rev are turned to None
            '3', 'extid', '', '', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj', 'who',
            'buildera', 'builderc'
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob['branch'], None)
        self.assertEqual(parsedjob['baserev'], None)

    def test_parseJob_v3_no_builders(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '3', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj', 'who'
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob['builderNames'], [])

    def test_parseJob_v3_no_properties(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '3', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj', 'who'
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob['properties'], {})

    def test_parseJob_v4(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '4', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj', 'who', 'comment',
            'buildera', 'builderc'
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob, {
            'baserev': '1234',
            'branch': 'trunk',
            'builderNames': ['buildera', 'builderc'],
            'jobid': 'extid',
            'patch_body': 'this is my diff, -- ++, etc.',
            'patch_level': 1,
            'project': 'proj',
            'who': 'who',
            'comment': 'comment',
            'repository': 'repo',
            'properties': {},
        })

    def test_parseJob_v4_empty_branch_rev(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            # blank branch, rev are turned to None
            '4', 'extid', '', '', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj', 'who', 'comment',
            'buildera', 'builderc'
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob['branch'], None)
        self.assertEqual(parsedjob['baserev'], None)

    def test_parseJob_v4_no_builders(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '4', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj', 'who', 'comment'
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob['builderNames'], [])

    def test_parseJob_v4_no_properties(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '4', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj', 'who', 'comment'
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob['properties'], {})

    def test_parseJob_v5(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '5',
            json.dumps({
                'jobid': 'extid', 'branch': 'trunk', 'baserev': '1234',
                'patch_level': 1, 'patch_body': 'this is my diff, -- ++, etc.',
                'repository': 'repo', 'project': 'proj', 'who': 'who',
                'comment': 'comment', 'builderNames': ['buildera', 'builderc'],
                'properties': {'foo': 'bar'},
            }))
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob, {
            'baserev': '1234',
            'branch': 'trunk',
            'builderNames': ['buildera', 'builderc'],
            'jobid': 'extid',
            'patch_body': 'this is my diff, -- ++, etc.',
            'patch_level': 1,
            'project': 'proj',
            'who': 'who',
            'comment': 'comment',
            'repository': 'repo',
            'properties': {'foo': 'bar'},
        })

    def test_parseJob_v5_empty_branch_rev(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            # blank branch, rev are turned to None
            '4', 'extid', '', '', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj', 'who', 'comment',
            'buildera', 'builderc'
        )
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob['branch'], None)
        self.assertEqual(parsedjob['baserev'], None)

    def test_parseJob_v5_no_builders(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '5',
            json.dumps({
                'jobid': 'extid', 'branch': 'trunk', 'baserev': '1234',
                'patch_level': '1', 'diff': 'this is my diff, -- ++, etc.',
                'repository': 'repo', 'project': 'proj', 'who': 'who',
                'comment': 'comment', 'builderNames': [],
                'properties': {'foo': 'bar'},
            }))
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob['builderNames'], [])

    def test_parseJob_v5_no_properties(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '5',
            json.dumps({
                'jobid': 'extid', 'branch': 'trunk', 'baserev': '1234',
                'patch_level': '1', 'diff': 'this is my diff, -- ++, etc.',
                'repository': 'repo', 'project': 'proj', 'who': 'who',
                'comment': 'comment', 'builderNames': ['buildera', 'builderb'],
                'properties': {},
            }))
        parsedjob = sched.parseJob(NativeStringIO(jobstr))
        self.assertEqual(parsedjob['properties'], {})

    def test_parseJob_v5_invalid_json(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring('5', '{"comment": "com}')
        self.assertRaises(
            trysched.BadJobfile, sched.parseJob, NativeStringIO(jobstr))

    # handleJobFile

    def call_handleJobFile(self, parseJob):
        sched = self.attachScheduler(
            trysched.Try_Jobdir(
                name='tsched', builderNames=['buildera', 'builderb'],
                jobdir='foo'), self.OBJECTID, self.SCHEDULERID,
            overrideBuildsetMethods=True,
            createBuilderDB=True)
        fakefile = mock.Mock()

        def parseJob_(f):
            assert f is fakefile
            return parseJob(f)
        sched.parseJob = parseJob_
        return defer.maybeDeferred(sched.handleJobFile, 'fakefile', fakefile)

    def makeSampleParsedJob(self, **overrides):
        pj = dict(baserev='1234', branch='trunk',
                  builderNames=['buildera', 'builderb'],
                  jobid='extid', patch_body='this is my diff, -- ++, etc.',
                  patch_level=1, project='proj', repository='repo', who='who',
                  comment='comment', properties={})
        pj.update(overrides)
        return pj

    def test_handleJobFile(self):
        d = self.call_handleJobFile(lambda f: self.makeSampleParsedJob())

        def check(_):
            self.assertEqual(self.addBuildsetCalls, [
                ('addBuildsetForSourceStamps', dict(
                    builderNames=['buildera', 'builderb'],
                    external_idstring=u'extid',
                    properties={},
                    reason=u"'try' job by user who",
                    sourcestamps=[
                        dict(
                            branch='trunk',
                            codebase='',
                            patch_author='who',
                            patch_body='this is my diff, -- ++, etc.',
                            patch_comment='comment',
                            patch_level=1,
                            patch_subdir='',
                            project='proj',
                            repository='repo',
                            revision='1234'),
                    ])),
            ])
        d.addCallback(check)
        return d

    def test_handleJobFile_exception(self):
        def parseJob(f):
            raise trysched.BadJobfile
        d = self.call_handleJobFile(parseJob)

        def check(bsid):
            self.assertEqual(self.addBuildsetCalls, [])
            self.assertEqual(
                1, len(self.flushLoggedErrors(trysched.BadJobfile)))
        d.addCallback(check)
        return d
    if twisted.version.major <= 9 and sys.version_info[:2] >= (2, 7):
        test_handleJobFile_exception.skip = (
            "flushLoggedErrors does not work correctly on 9.0.0 "
            "and earlier with Python-2.7")

    def test_handleJobFile_bad_builders(self):
        d = self.call_handleJobFile(
            lambda f: self.makeSampleParsedJob(builderNames=['xxx']))

        def check(_):
            self.assertEqual(self.addBuildsetCalls, [])
        d.addCallback(check)
        return d

    def test_handleJobFile_subset_builders(self):
        d = self.call_handleJobFile(
            lambda f: self.makeSampleParsedJob(builderNames=['buildera']))

        def check(_):
            self.assertEqual(self.addBuildsetCalls, [
                ('addBuildsetForSourceStamps', dict(
                    builderNames=['buildera'],
                    external_idstring=u'extid',
                    properties={},
                    reason=u"'try' job by user who",
                    sourcestamps=[
                        dict(
                            branch='trunk',
                            codebase='',
                            patch_author='who',
                            patch_body='this is my diff, -- ++, etc.',
                            patch_comment='comment',
                            patch_level=1,
                            patch_subdir='',
                            project='proj',
                            repository='repo',
                            revision='1234'),
                    ])),
            ])
        d.addCallback(check)
        return d

    def test_handleJobFile_with_try_properties(self):
        d = self.call_handleJobFile(
            lambda f: self.makeSampleParsedJob(properties={'foo': 'bar'}))

        def check(_):
            self.assertEqual(self.addBuildsetCalls, [
                ('addBuildsetForSourceStamps', dict(
                    builderNames=['buildera', 'builderb'],
                    external_idstring=u'extid',
                    properties={'foo': ('bar', u'try build')},
                    reason=u"'try' job by user who",
                    sourcestamps=[
                        dict(
                            branch='trunk',
                            codebase='',
                            patch_author='who',
                            patch_body='this is my diff, -- ++, etc.',
                            patch_comment='comment',
                            patch_level=1,
                            patch_subdir='',
                            project='proj',
                            repository='repo',
                            revision='1234'),
                    ])),
            ])
        d.addCallback(check)
        return d

    def test_handleJobFile_with_invalid_try_properties(self):
        d = self.call_handleJobFile(
            lambda f: self.makeSampleParsedJob(properties=['foo', 'bar']))
        return self.assertFailure(d, AttributeError)


class Try_Userpass_Perspective(scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 26
    SCHEDULERID = 6

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    def makeScheduler(self, **kwargs):
        sched = self.attachScheduler(trysched.Try_Userpass(**kwargs),
                                     self.OBJECTID, self.SCHEDULERID,
                                     overrideBuildsetMethods=True,
                                     createBuilderDB=True)
        # Try will return a remote version of master.status, so give it
        # something to return
        sched.master.status = mock.Mock()
        return sched

    def call_perspective_try(self, *args, **kwargs):
        sched = self.makeScheduler(name='tsched', builderNames=['a', 'b'],
                                   port='xxx', userpass=[('a', 'b')], properties=dict(frm='schd'))
        persp = trysched.Try_Userpass_Perspective(sched, 'a')

        # patch out all of the handling after addBuildsetForSourceStamp
        def getBuildset(bsid):
            return dict(bsid=bsid)
        self.db.buildsets.getBuildset = getBuildset

        d = persp.perspective_try(*args, **kwargs)

        def check(rbss):
            if rbss is None:
                return
            self.assertIsInstance(rbss, trysched.RemoteBuildSetStatus)
        d.addCallback(check)
        return d

    def test_perspective_try(self):
        d = self.call_perspective_try(
            'default', 'abcdef', (1, '-- ++'), 'repo', 'proj', ['a'],
            properties={'pr': 'op'})

        def check(_):
            self.assertEqual(self.addBuildsetCalls, [
                ('addBuildsetForSourceStamps', dict(
                    builderNames=['a'],
                    external_idstring=None,
                    properties={'pr': ('op', u'try build')},
                    reason=u"'try' job",
                    sourcestamps=[
                        dict(
                            branch='default',
                            codebase='',
                            patch_author='',
                            patch_body='-- ++',
                            patch_comment='',
                            patch_level=1,
                            patch_subdir='',
                            project='proj',
                            repository='repo',
                            revision='abcdef'),
                    ])),
            ])
        d.addCallback(check)
        return d

    def test_perspective_try_who(self):
        d = self.call_perspective_try(
            'default', 'abcdef', (1, '-- ++'), 'repo', 'proj', ['a'],
            who='who', comment='comment', properties={'pr': 'op'})

        def check(_):
            self.assertEqual(self.addBuildsetCalls, [
                ('addBuildsetForSourceStamps', dict(
                    builderNames=['a'],
                    external_idstring=None,
                    properties={'pr': ('op', u'try build')},
                    reason=u"'try' job by user who (comment)",
                    sourcestamps=[
                        dict(
                            branch='default',
                            codebase='',
                            patch_author='who',
                            patch_body='-- ++',
                            patch_comment='comment',
                            patch_level=1,
                            patch_subdir='',
                            project='proj',
                            repository='repo',
                            revision='abcdef'),
                    ])),
            ])
        d.addCallback(check)
        return d

    def test_perspective_try_bad_builders(self):
        d = self.call_perspective_try(
            'default', 'abcdef', (1, '-- ++'), 'repo', 'proj', ['xxx'],
            properties={'pr': 'op'})

        def check(_):
            self.assertEqual(self.addBuildsetCalls, [])
        d.addCallback(check)
        return d

    def test_getAvailableBuilderNames(self):
        sched = self.makeScheduler(name='tsched', builderNames=['a', 'b'],
                                   port='xxx', userpass=[('a', 'b')])
        persp = trysched.Try_Userpass_Perspective(sched, 'a')
        d = defer.maybeDeferred(persp.perspective_getAvailableBuilderNames)

        def check(buildernames):
            self.assertEqual(buildernames, ['a', 'b'])
        d.addCallback(check)
        return d


class Try_Userpass(scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 25
    SCHEDULERID = 5

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    def makeScheduler(self, **kwargs):
        sched = self.attachScheduler(trysched.Try_Userpass(**kwargs),
                                     self.OBJECTID, self.SCHEDULERID)
        return sched

    def test_service(self):
        sched = self.makeScheduler(name='tsched', builderNames=['a'],
                                   port='tcp:9999', userpass=[('fred', 'derf')])
        # patch out the pbmanager's 'register' command both to be sure
        # the registration is correct and to get a copy of the factory
        registration = mock.Mock()
        registration.unregister = lambda: defer.succeed(None)
        sched.master.pbmanager = mock.Mock()

        def register(portstr, user, passwd, factory):
            self.assertEqual([portstr, user, passwd],
                             ['tcp:9999', 'fred', 'derf'])
            self.got_factory = factory
            return registration
        sched.master.pbmanager.register = register
        # start it
        sched.startService()
        # make a fake connection by invoking the factory, and check that we
        # get the correct perspective
        persp = self.got_factory(mock.Mock(), 'fred')
        self.assertTrue(isinstance(persp, trysched.Try_Userpass_Perspective))
        return sched.stopService()

    @defer.inlineCallbacks
    def test_service_but_not_active(self):
        sched = self.makeScheduler(name='tsched', builderNames=['a'],
                                   port='tcp:9999', userpass=[('fred', 'derf')])

        self.setSchedulerToMaster(self.OTHER_MASTER_ID)

        sched.master.pbmanager = mock.Mock()

        sched.startService()
        yield sched.stopService()

        self.assertFalse(sched.master.pbmanager.register.called)
