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

from __future__ import with_statement

import cStringIO as StringIO
import mock
import os
import shutil
import sys

import twisted

from buildbot.schedulers import trysched
from buildbot.test.util import dirs
from buildbot.test.util import scheduler
from buildbot.util import json
from twisted.internet import defer
from twisted.protocols import basic
from twisted.trial import unittest


class TryBase(unittest.TestCase):

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
        svc = trysched.JobdirService(self.jobdir)

        # creat some new data to process
        jobdata = os.path.join(self.newdir, 'jobdata')
        with open(jobdata, "w") as f:
            f.write('JOBDATA')

        # stub out svc.parent.handleJobFile and .jobdir
        def handleJobFile(filename, f):
            self.assertEqual(filename, 'jobdata')
            self.assertEqual(f.read(), 'JOBDATA')
        svc.parent = mock.Mock()
        svc.parent.handleJobFile = handleJobFile
        svc.parent.jobdir = self.jobdir

        # run it
        svc.messageReceived('jobdata')


class Try_Jobdir(scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 23

    def setUp(self):
        self.setUpScheduler()
        self.jobdir = None

    def tearDown(self):
        self.tearDownScheduler()
        if self.jobdir:
            shutil.rmtree(self.jobdir)

    # tests

    def do_test_startService(self, jobdir, exp_jobdir):
        # set up jobdir
        self.jobdir = os.path.abspath('jobdir')
        if os.path.exists(self.jobdir):
            shutil.rmtree(self.jobdir)
        os.mkdir(self.jobdir)

        # build scheduler
        kwargs = dict(name="tsched", builderNames=['a'], jobdir=self.jobdir)
        sched = self.attachScheduler(
            trysched.Try_Jobdir(**kwargs), self.OBJECTID)

        # start it
        sched.startService()

        # check that it has set the basedir correctly
        self.assertEqual(sched.watcher.basedir, self.jobdir)

        return sched.stopService()

    def test_startService_reldir(self):
        return self.do_test_startService(
            'jobdir',
            os.path.abspath('basedir/jobdir'))

    def test_startService_reldir_subdir(self):
        return self.do_test_startService(
            'jobdir',
            os.path.abspath('basedir/jobdir/cur'))

    def test_startService_absdir(self):
        return self.do_test_startService(
            os.path.abspath('jobdir'),
            os.path.abspath('jobdir'))

    # parseJob

    def test_parseJob_empty(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['a'], jobdir='foo')
        self.assertRaises(
            trysched.BadJobfile, sched.parseJob, StringIO.StringIO(''))

    def test_parseJob_longer_than_netstring_MAXLENGTH(self):
        self.patch(basic.NetstringReceiver, 'MAX_LENGTH', 100)
        sched = trysched.Try_Jobdir(name='tsched', builderNames=['a'], jobdir='foo')
        jobstr = self.makeNetstring(
            '1', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'buildera', 'builderc'
        )
        jobstr += 'x' * 200

        test_temp_file = StringIO.StringIO(jobstr)

        self.assertRaises(trysched.BadJobfile,
                          lambda: sched.parseJob(test_temp_file))

    def test_parseJob_invalid(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['a'], jobdir='foo')
        self.assertRaises(
            trysched.BadJobfile, sched.parseJob,
            StringIO.StringIO('this is not a netstring'))

    def test_parseJob_invalid_version(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['a'], jobdir='foo')
        self.assertRaises(
            trysched.BadJobfile, sched.parseJob, StringIO.StringIO('1:9,'))

    def makeNetstring(self, *strings):
        return ''.join(['%d:%s,' % (len(s), s) for s in strings])

    def test_parseJob_v1(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '1', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'buildera', 'builderc'
        )
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
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
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
        self.assertEqual(parsedjob['branch'], None)
        self.assertEqual(parsedjob['baserev'], None)

    def test_parseJob_v1_no_builders(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '1', 'extid', '', '', '1', 'this is my diff, -- ++, etc.'
        )
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
        self.assertEqual(parsedjob['builderNames'], [])

    def test_parseJob_v1_no_properties(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '1', 'extid', '', '', '1', 'this is my diff, -- ++, etc.'
        )
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
        self.assertEqual(parsedjob['properties'], {})

    def test_parseJob_v2(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '2', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj',
            'buildera', 'builderc'
        )
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
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
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
        self.assertEqual(parsedjob['branch'], None)
        self.assertEqual(parsedjob['baserev'], None)

    def test_parseJob_v2_no_builders(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '2', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj',
        )
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
        self.assertEqual(parsedjob['builderNames'], [])

    def test_parseJob_v2_no_properties(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '2', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj',
        )
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
        self.assertEqual(parsedjob['properties'], {})

    def test_parseJob_v3(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '3', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj', 'who',
            'buildera', 'builderc'
        )
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
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
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
        self.assertEqual(parsedjob['branch'], None)
        self.assertEqual(parsedjob['baserev'], None)

    def test_parseJob_v3_no_builders(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '3', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj', 'who'
        )
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
        self.assertEqual(parsedjob['builderNames'], [])

    def test_parseJob_v3_no_properties(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '3', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj', 'who'
        )
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
        self.assertEqual(parsedjob['properties'], {})

    def test_parseJob_v4(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '4', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj', 'who', 'comment',
            'buildera', 'builderc'
        )
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
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
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
        self.assertEqual(parsedjob['branch'], None)
        self.assertEqual(parsedjob['baserev'], None)

    def test_parseJob_v4_no_builders(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '4', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj', 'who', 'comment'
        )
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
        self.assertEqual(parsedjob['builderNames'], [])

    def test_parseJob_v4_no_properties(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring(
            '4', 'extid', 'trunk', '1234', '1', 'this is my diff, -- ++, etc.',
            'repo', 'proj', 'who', 'comment'
        )
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
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
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
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
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
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
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
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
        parsedjob = sched.parseJob(StringIO.StringIO(jobstr))
        self.assertEqual(parsedjob['properties'], {})

    def test_parseJob_v5_invalid_json(self):
        sched = trysched.Try_Jobdir(
            name='tsched', builderNames=['buildera', 'builderb'], jobdir='foo')
        jobstr = self.makeNetstring('5', '{"comment": "com}')
        self.assertRaises(
            trysched.BadJobfile, sched.parseJob, StringIO.StringIO(jobstr))

    # handleJobFile

    def call_handleJobFile(self, parseJob):
        sched = self.attachScheduler(
            trysched.Try_Jobdir(
                name='tsched', builderNames=['buildera', 'builderb'],
                jobdir='foo'), self.OBJECTID)
        fakefile = mock.Mock()

        def parseJob_(f):
            assert f is fakefile
            return parseJob(f)
        sched.parseJob = parseJob_
        return sched.handleJobFile('fakefile', fakefile)

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
            self.db.buildsets.assertBuildset('?',
                                             dict(reason="'try' job by user who",
                                                  external_idstring='extid',
                                                  properties=[('scheduler', ('tsched', 'Scheduler'))],
                                                  sourcestampsetid=100),
                                             {'':
                                              dict(branch='trunk', repository='repo', codebase='',
                                                   project='proj', revision='1234',
                                                   patch_body='this is my diff, -- ++, etc.',
                                                   patch_level=1, patch_subdir='',
                                                   patch_author='who',
                                                   patch_comment='comment',
                                                   sourcestampsetid=100)
                                              })
        d.addCallback(check)
        return d

    def test_handleJobFile_exception(self):
        def parseJob(f):
            raise trysched.BadJobfile
        d = self.call_handleJobFile(parseJob)

        def check(bsid):
            self.db.buildsets.assertBuildsets(0)
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
            self.db.buildsets.assertBuildsets(0)
        d.addCallback(check)
        return d

    def test_handleJobFile_subset_builders(self):
        d = self.call_handleJobFile(
            lambda f: self.makeSampleParsedJob(builderNames=['buildera']))

        def check(_):
            self.db.buildsets.assertBuildset('?',
                                             dict(reason="'try' job by user who",
                                                  external_idstring='extid',
                                                  properties=[('scheduler', ('tsched', 'Scheduler'))],
                                                  sourcestampsetid=100),
                                             {'':
                                              dict(branch='trunk', repository='repo', codebase='',
                                                   project='proj', revision='1234',
                                                   patch_body='this is my diff, -- ++, etc.',
                                                   patch_level=1, patch_subdir='',
                                                   patch_author='who',
                                                   patch_comment='comment',
                                                   sourcestampsetid=100)
                                              })
        d.addCallback(check)
        return d

    def test_handleJobFile_with_try_properties(self):
        d = self.call_handleJobFile(
            lambda f: self.makeSampleParsedJob(properties={'foo': 'bar'}))

        def check(_):
            self.db.buildsets.assertBuildset('?',
                                             dict(reason="'try' job by user who",
                                                  external_idstring='extid',
                                                  properties=[
                                                      ('foo', ('bar', 'try build')),
                                                      ('scheduler', ('tsched', 'Scheduler')),
                                                  ],
                                                  sourcestampsetid=100),
                                             {'':
                                              dict(branch='trunk', repository='repo', codebase='',
                                                   project='proj', revision='1234',
                                                   patch_body='this is my diff, -- ++, etc.',
                                                   patch_level=1, patch_subdir='',
                                                   patch_author='who',
                                                   patch_comment='comment',
                                                   sourcestampsetid=100)
                                              })
        d.addCallback(check)
        return d

    def test_handleJobFile_with_invalid_try_properties(self):
        d = self.call_handleJobFile(
            lambda f: self.makeSampleParsedJob(properties=['foo', 'bar']))
        return self.assertFailure(d, AttributeError)


class Try_Userpass_Perspective(scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 26

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    def makeScheduler(self, **kwargs):
        sched = self.attachScheduler(trysched.Try_Userpass(**kwargs),
                                     self.OBJECTID)
        # Try will return a remote version of master.status, so give it
        # something to return
        sched.master.status = mock.Mock()
        return sched

    def call_perspective_try(self, *args, **kwargs):
        sched = self.makeScheduler(name='tsched', builderNames=['a', 'b'],
                                   port='xxx', userpass=[('a', 'b')], properties=dict(frm='schd'))
        persp = trysched.Try_Userpass_Perspective(sched, 'a')
        return persp.perspective_try(*args, **kwargs)

    def test_perspective_try(self):
        d = self.call_perspective_try(
            'default', 'abcdef', (1, '-- ++'), 'repo', 'proj', ['a'],
            properties={'pr': 'op'})

        def check(_):
            self.db.buildsets.assertBuildset('?',
                                             dict(reason="'try' job",
                                                  external_idstring=None,
                                                  properties=[
                                                      ('frm', ('schd', 'Scheduler')),
                                                      ('pr', ('op', 'try build')),
                                                      ('scheduler', ('tsched', 'Scheduler')),
                                                  ],
                                                  sourcestampsetid=100,
                                                  ),
                                             {'':
                                              dict(branch='default', repository='repo', codebase='',
                                                   project='proj', revision='abcdef',
                                                   sourcestampsetid=100,
                                                   patch_body='-- ++', patch_level=1, patch_subdir='',
                                                   patch_author="", patch_comment="")
                                              })
        d.addCallback(check)
        return d

    def test_perspective_try_who(self):
        d = self.call_perspective_try(
            'default', 'abcdef', (1, '-- ++'), 'repo', 'proj', ['a'],
            who='who', comment='comment', properties={'pr': 'op'})

        def check(_):
            self.db.buildsets.assertBuildset('?',
                                             dict(reason="'try' job by user who (comment)",
                                                  external_idstring=None,
                                                  properties=[
                                                      ('frm', ('schd', 'Scheduler')),
                                                      ('pr', ('op', 'try build')),
                                                      ('scheduler', ('tsched', 'Scheduler')),
                                                  ],
                                                  sourcestampsetid=100,
                                                  ),
                                             {'':
                                              dict(branch='default', repository='repo', codebase='',
                                                   project='proj', revision='abcdef',
                                                   sourcestampsetid=100,
                                                   patch_body='-- ++', patch_level=1, patch_subdir='',
                                                   patch_author='who', patch_comment="comment")
                                              })
        d.addCallback(check)
        return d

    def test_perspective_try_bad_builders(self):
        d = self.call_perspective_try(
            'default', 'abcdef', (1, '-- ++'), 'repo', 'proj', ['xxx'],
            properties={'pr': 'op'})

        def check(_):
            self.db.buildsets.assertBuildsets(0)
        d.addCallback(check)
        return d

    def test_getAvailableBuilderNames(self):
        sched = self.makeScheduler(name='tsched', builderNames=['a', 'b'],
                                   port='xxx', userpass=[('a', 'b')])
        persp = trysched.Try_Userpass_Perspective(sched, 'a')
        d = defer.maybeDeferred(
            lambda: persp.perspective_getAvailableBuilderNames())

        def check(buildernames):
            self.assertEqual(buildernames, ['a', 'b'])
        d.addCallback(check)
        return d


class Try_Userpass(scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 25

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    def makeScheduler(self, **kwargs):
        sched = self.attachScheduler(trysched.Try_Userpass(**kwargs),
                                     self.OBJECTID)
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
        self.failUnless(isinstance(persp, trysched.Try_Userpass_Perspective))
        return sched.stopService()
