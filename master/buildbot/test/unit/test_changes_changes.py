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

import pprint
import re
import textwrap

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.changes import changes
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster


class Change(unittest.TestCase):

    change23_rows = [
        fakedb.Change(changeid=23, author="dustin", comments="fix whitespace",
                      branch="warnerdb", revision="deadbeef",
                      when_timestamp=266738404, revlink='http://warner/0e92a098b',
                      category='devel', repository='git://warner', codebase='mainapp',
                      project='Buildbot'),

        fakedb.ChangeFile(changeid=23, filename='master/README.txt'),
        fakedb.ChangeFile(changeid=23, filename='worker/README.txt'),

        fakedb.ChangeProperty(changeid=23, property_name='notest',
                              property_value='["no","Change"]'),

        fakedb.ChangeUser(changeid=23, uid=27),
    ]

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self, wantDb=True)
        self.change23 = changes.Change(**dict(  # using **dict(..) forces kwargs
            category='devel',
            repository=u'git://warner',
            codebase=u'mainapp',
            who=u'dustin',
            when=266738404,
            comments=u'fix whitespace',
            project=u'Buildbot',
            branch=u'warnerdb',
            revlink=u'http://warner/0e92a098b',
            properties={'notest': "no"},
            files=[u'master/README.txt', u'worker/README.txt'],
            revision=u'deadbeef'))
        self.change23.number = 23

        self.change24 = changes.Change(**dict(
            category='devel',
            repository=u'git://warner',
            codebase=u'mainapp',
            who=u'dustin',
            when=266738405,
            comments=u'fix whitespace again',
            project=u'Buildbot',
            branch=u'warnerdb',
            revlink=u'http://warner/0e92a098c',
            properties={'notest': "no"},
            files=[u'master/README.txt', u'worker/README.txt'],
            revision=u'deadbeef'))
        self.change24.number = 24

        self.change25 = changes.Change(**dict(
            category='devel',
            repository=u'git://warner',
            codebase=u'mainapp',
            who=u'dustin',
            when=266738406,
            comments=u'fix whitespace again',
            project=u'Buildbot',
            branch=u'warnerdb',
            revlink=u'http://warner/0e92a098d',
            properties={'notest': "no"},
            files=[u'master/README.txt', u'worker/README.txt'],
            revision=u'deadbeef'))
        self.change25.number = 25

    @defer.inlineCallbacks
    def test_fromChdict(self):
        # get a real honest-to-goodness chdict from the fake db
        yield self.master.db.insertTestData(self.change23_rows)
        chdict = yield self.master.db.changes.getChange(23)

        exp = self.change23
        got = yield changes.Change.fromChdict(self.master, chdict)

        # compare
        ok = True
        ok = ok and got.number == exp.number
        ok = ok and got.who == exp.who
        ok = ok and sorted(got.files) == sorted(exp.files)
        ok = ok and got.comments == exp.comments
        ok = ok and got.revision == exp.revision
        ok = ok and got.when == exp.when
        ok = ok and got.branch == exp.branch
        ok = ok and got.category == exp.category
        ok = ok and got.revlink == exp.revlink
        ok = ok and got.properties == exp.properties
        ok = ok and got.repository == exp.repository
        ok = ok and got.codebase == exp.codebase
        ok = ok and got.project == exp.project
        if not ok:
            def printable(c):
                return pprint.pformat(c.__dict__)
            self.fail("changes do not match; expected\n%s\ngot\n%s" %
                      (printable(exp), printable(got)))

    def test_str(self):
        string = str(self.change23)
        self.assertTrue(re.match(r"Change\(.*\)", string), string)

    def test_asText(self):
        text = self.change23.asText()
        self.assertTrue(re.match(textwrap.dedent(u'''\
            Files:
             master/README.txt
             worker/README.txt
            On: git://warner
            For: Buildbot
            At: .*
            Changed By: dustin
            Comments: fix whitespaceProperties:.
              notest: no

            '''), text), text)

    def test_asDict(self):
        dict = self.change23.asDict()
        self.assertIn('1978', dict['at'])  # timezone-sensitive
        del dict['at']
        self.assertEqual(dict, {
            'branch': u'warnerdb',
            'category': u'devel',
            'codebase': u'mainapp',
            'comments': u'fix whitespace',
            'files': [{'name': u'master/README.txt'},
                      {'name': u'worker/README.txt'}],
            'number': 23,
            'project': u'Buildbot',
            'properties': [('notest', 'no', 'Change')],
            'repository': u'git://warner',
            'rev': u'deadbeef',
            'revision': u'deadbeef',
            'revlink': u'http://warner/0e92a098b',
            'when': 266738404,
            'who': u'dustin'})

    def test_getShortAuthor(self):
        self.assertEqual(self.change23.getShortAuthor(), 'dustin')

    def test_getTime(self):
        # careful, or timezones will hurt here
        self.assertIn('Jun 1978', self.change23.getTime())

    def test_getTimes(self):
        self.assertEqual(self.change23.getTimes(), (266738404, None))

    def test_getText(self):
        self.change23.who = 'nasty < nasty'  # test the html escaping (ugh!)
        self.assertEqual(self.change23.getText(), ['nasty &lt; nasty'])

    def test_getLogs(self):
        self.assertEqual(self.change23.getLogs(), {})

    def test_compare(self):
        self.assertEqual(self.change23, self.change23)
        self.assertNotEqual(self.change24, self.change23)
        self.assertGreater(self.change24, self.change23)
        self.assertGreaterEqual(self.change24, self.change23)
        self.assertGreaterEqual(self.change24, self.change24)
        self.assertLessEqual(self.change24, self.change24)
        self.assertLessEqual(self.change23, self.change24)
        self.assertLess(self.change23, self.change25)
