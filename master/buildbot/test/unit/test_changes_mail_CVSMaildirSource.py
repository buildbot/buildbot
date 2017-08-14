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

from email import message_from_string
from email.utils import mktime_tz
from email.utils import parsedate_tz

from twisted.trial import unittest

from buildbot.changes.mail import CVSMaildirSource

#
# Sample message from CVS version 1.11
#

cvs1_11_msg = """From: Andy Howell <andy@example.com>
To: buildbot@example.com
Subject: cvs module MyModuleName
Date: Sat, 07 Aug 2010 11:11:49 +0000
X-Mailer: Python buildbot-cvs-mail $Revision: 1.3 $

Cvsmode: 1.11
Category: None
CVSROOT: :ext:cvshost.example.com:/cvsroot
Files: base/module/src/make GNUmakefile,1.362,1.363
Project: MyModuleName
Update of /cvsroot/base/moduel/src/make
In directory cvshost:/tmp/cvs-serv10922

Modified Files:
        GNUmakefile
Log Message:
Commented out some stuff.
"""

#
# Sample message from CVS version 1.12
#
# Paths are handled differently by the two versions
#

cvs1_12_msg = """Date: Wed, 11 Aug 2010 04:56:44 +0000
From: andy@example.com
To: buildbot@example.com
Subject: cvs update for project RaiCore
X-Mailer: Python buildbot-cvs-mail $Revision: 1.3 $

Cvsmode: 1.12
Category: None
CVSROOT: :ext:cvshost.example.com:/cvsroot
Files: file1.cpp 1.77 1.78 file2.cpp 1.75 1.76
Path: base/module/src
Project: MyModuleName
Update of /cvsroot/base/module/src
In directory example.com:/tmp/cvs-serv26648/InsightMonAgent

Modified Files:
        file1.cpp file2.cpp
Log Message:
Changes for changes sake
"""


class TestCVSMaildirSource(unittest.TestCase):

    def test_CVSMaildirSource_create_change_from_cvs1_11msg(self):
        m = message_from_string(cvs1_11_msg)
        src = CVSMaildirSource('/dev/null')
        src, chdict = src.parse(m)
        self.assertNotEqual(chdict, None)
        self.assertEqual(chdict['author'], 'andy')
        self.assertEqual(len(chdict['files']), 1)
        self.assertEqual(
            chdict['files'][0], 'base/module/src/make/GNUmakefile')
        self.assertEqual(chdict['comments'], 'Commented out some stuff.\n')
        self.assertFalse(chdict['isdir'])
        self.assertEqual(chdict['revision'], '2010-08-07 11:11:49')
        dateTuple = parsedate_tz('Sat, 07 Aug 2010 11:11:49 +0000')
        self.assertEqual(chdict['when'], mktime_tz(dateTuple))
        self.assertEqual(chdict['branch'], None)
        self.assertEqual(
            chdict['repository'], ':ext:cvshost.example.com:/cvsroot')
        self.assertEqual(chdict['project'], 'MyModuleName')
        self.assertEqual(len(chdict['properties']), 0)
        self.assertEqual(src, 'cvs')

    def test_CVSMaildirSource_create_change_from_cvs1_12msg(self):
        m = message_from_string(cvs1_12_msg)
        src = CVSMaildirSource('/dev/null')
        src, chdict = src.parse(m)
        self.assertNotEqual(chdict, None)
        self.assertEqual(chdict['author'], 'andy')
        self.assertEqual(len(chdict['files']), 2)
        self.assertEqual(chdict['files'][0], 'base/module/src/file1.cpp')
        self.assertEqual(chdict['files'][1], 'base/module/src/file2.cpp')
        self.assertEqual(chdict['comments'], 'Changes for changes sake\n')
        self.assertFalse(chdict['isdir'])
        self.assertEqual(chdict['revision'], '2010-08-11 04:56:44')
        dateTuple = parsedate_tz('Wed, 11 Aug 2010 04:56:44 +0000')
        self.assertEqual(chdict['when'], mktime_tz(dateTuple))
        self.assertEqual(chdict['branch'], None)
        self.assertEqual(
            chdict['repository'], ':ext:cvshost.example.com:/cvsroot')
        self.assertEqual(chdict['project'], 'MyModuleName')
        self.assertEqual(len(chdict['properties']), 0)
        self.assertEqual(src, 'cvs')

    def test_CVSMaildirSource_create_change_from_cvs1_12_with_no_path(self):
        msg = cvs1_12_msg.replace('Path: base/module/src', '')
        m = message_from_string(msg)
        src = CVSMaildirSource('/dev/null')
        try:
            assert src.parse(m)[1]
        except ValueError:
            pass
        else:
            self.fail('Expect ValueError.')

    def test_CVSMaildirSource_create_change_with_bad_cvsmode(self):
        # Branch is indicated after 'Tag:' in modified file list
        msg = cvs1_11_msg.replace('Cvsmode: 1.11', 'Cvsmode: 9.99')
        m = message_from_string(msg)
        src = CVSMaildirSource('/dev/null')
        try:
            assert src.parse(m)[1]
        except ValueError:
            pass
        else:
            self.fail('Expected ValueError')

    def test_CVSMaildirSource_create_change_with_branch(self):
        # Branch is indicated after 'Tag:' in modified file list
        msg = cvs1_11_msg.replace('        GNUmakefile',
                                  '      Tag: Test_Branch\n      GNUmakefile')
        m = message_from_string(msg)
        src = CVSMaildirSource('/dev/null')
        chdict = src.parse(m)[1]
        self.assertEqual(chdict['branch'], 'Test_Branch')

    def test_CVSMaildirSource_create_change_with_category(self):
        msg = cvs1_11_msg.replace('Category: None', 'Category: Test category')
        m = message_from_string(msg)
        src = CVSMaildirSource('/dev/null')
        chdict = src.parse(m)[1]
        self.assertEqual(chdict['category'], 'Test category')

    def test_CVSMaildirSource_create_change_with_no_comment(self):
        # Strip off comments
        msg = cvs1_11_msg[:cvs1_11_msg.find('Commented out some stuff')]
        m = message_from_string(msg)
        src = CVSMaildirSource('/dev/null')
        chdict = src.parse(m)[1]
        self.assertEqual(chdict['comments'], None)

    def test_CVSMaildirSource_create_change_with_no_files(self):
        # A message with no files is likely not for us
        msg = cvs1_11_msg.replace(
            'Files: base/module/src/make GNUmakefile,1.362,1.363', '')
        m = message_from_string(msg)
        src = CVSMaildirSource('/dev/null')
        chdict = src.parse(m)
        self.assertEqual(chdict, None)

    def test_CVSMaildirSource_create_change_with_no_project(self):
        msg = cvs1_11_msg.replace('Project: MyModuleName', '')
        m = message_from_string(msg)
        src = CVSMaildirSource('/dev/null')
        chdict = src.parse(m)[1]
        self.assertEqual(chdict['project'], None)

    def test_CVSMaildirSource_create_change_with_no_repository(self):
        msg = cvs1_11_msg.replace(
            'CVSROOT: :ext:cvshost.example.com:/cvsroot', '')
        m = message_from_string(msg)
        src = CVSMaildirSource('/dev/null')
        chdict = src.parse(m)[1]
        self.assertEqual(chdict['repository'], None)

    def test_CVSMaildirSource_create_change_with_property(self):
        m = message_from_string(cvs1_11_msg)
        propDict = {'foo': 'bar'}
        src = CVSMaildirSource('/dev/null', properties=propDict)
        chdict = src.parse(m)[1]
        self.assertEqual(chdict['properties']['foo'], 'bar')
