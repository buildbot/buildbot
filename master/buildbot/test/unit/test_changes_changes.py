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

import textwrap
import re
from twisted.trial import unittest
from buildbot.test.fake import fakedb
from buildbot.changes import changes

class Change(unittest.TestCase):

    change23_rows = [
        fakedb.Change(changeid=23, author="dustin", comments="fix whitespace",
            is_dir=0, branch="warnerdb", revision="deadbeef",
            when_timestamp=266738404, revlink='http://warner/0e92a098b',
            category='devel', repository='git://warner', codebase='mainapp',
            project='Buildbot'),

        fakedb.ChangeFile(changeid=23, filename='master/README.txt'),
        fakedb.ChangeFile(changeid=23, filename='slave/README.txt'),

        fakedb.ChangeProperty(changeid=23, property_name='notest',
            property_value='["no","Change"]'),

        fakedb.ChangeUser(changeid=23, uid=27),
    ]

    def setUp(self):
        self.change23 = changes.Change(**dict( # using **dict(..) forces kwargs
            category='devel',
            isdir=0,
            repository=u'git://warner',
            codebase=u'mainapp',
            who=u'dustin',
            when=266738404,
            comments=u'fix whitespace',
            project=u'Buildbot',
            branch=u'warnerdb',
            revlink=u'http://warner/0e92a098b',
            properties={'notest':"no"},
            files=[u'master/README.txt', u'slave/README.txt'],
            revision=u'deadbeef'))
        self.change23.number = 23

    def test_str(self):
        string = str(self.change23)
        self.assertTrue(re.match(r"Change\(.*\)", string), string)

    def test_asText(self):
        text = self.change23.asText()
        self.assertTrue(re.match(textwrap.dedent(u'''\
            Files:
             master/README.txt
             slave/README.txt
            On: git://warner
            For: Buildbot
            At: .*
            Changed By: dustin
            Comments: fix whitespaceProperties: 
              notest: no

            '''), text), text)

    def test_asDict(self):
        dict = self.change23.asDict()
        self.assertIn('1978', dict['at']) # timezone-sensitive
        del dict['at']
        self.assertEqual(dict, {
            'branch': u'warnerdb',
            'category': u'devel',
            'codebase': u'mainapp',
            'comments': u'fix whitespace',
            'files': [{'name': u'master/README.txt'},
                      {'name': u'slave/README.txt'}],
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
        self.change23.who = 'nasty < nasty' # test the html escaping (ugh!)
        self.assertEqual(self.change23.getText(), ['nasty &lt; nasty'])

    def test_getLogs(self):
        self.assertEqual(self.change23.getLogs(), {})

