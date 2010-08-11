from mock import Mock, patch_object
from buildbot.interfaces import ParameterError
from twisted.trial import unittest

from email import message_from_string
from email.Utils import parseaddr, parsedate_tz, mktime_tz
import datetime
from buildbot.status.builder import SUCCESS, FAILURE
from buildbot.changes.mail import MaildirSource, BuildbotCVSMaildirSource

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

cvs1_12_msg="""Date: Wed, 11 Aug 2010 04:56:44 +0000
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

def fileToUrl( file, oldRev, newRev ):
    return 'http://example.com/cgi-bin/cvsweb.cgi/' + file + '?rev=' + newRev

class TestMaildirSource(unittest.TestCase):
    def test_BuildbotCVSMaildirSource_create_change_from_cvs1_11msg(self):
        build = Mock()
        m = message_from_string(cvs1_11_msg)
        src = BuildbotCVSMaildirSource('/dev/null', urlmaker=fileToUrl)
        try:
            change = src.parse( m )
        except UnicodeEncodeError:
            self.fail('Failed to get change from email message.')
        self.assert_(change != None)
        self.assert_(change.who == 'andy')
        self.assert_(len(change.files) == 1)
        self.assert_(change.files[0] == 'base/module/src/make/GNUmakefile')
        self.assert_(change.comments == 'Commented out some stuff.\n')
        self.assert_(change.isdir == False)
        self.assert_(len(change.links) == 1)
        self.assert_(change.revision == '2010-08-07 11:11:49')
        dateTuple = parsedate_tz('Sat, 07 Aug 2010 11:11:49 +0000')
        self.assert_(change.when == mktime_tz(dateTuple))
        self.assert_(change.branch == None)
        self.assert_(change.revlink == '')
        self.assert_(change.repository == ':ext:cvshost.example.com:/cvsroot')
        self.assert_(change.project == 'MyModuleName')

    def test_BuildbotCVSMaildirSource_create_change_from_cvs1_12msg(self):
        build = Mock()
        m = message_from_string(cvs1_12_msg)
        src = BuildbotCVSMaildirSource('/dev/null', urlmaker=fileToUrl)
        try:
            change = src.parse( m )
        except UnicodeEncodeError:
            self.fail('Failed to get change from email message.')
        self.assert_(change != None)
        self.assert_(change.who == 'andy')
        self.assert_(len(change.files) == 2)
        self.assert_(change.files[0] == 'base/module/src/file1.cpp')
        self.assert_(change.files[1] == 'base/module/src/file2.cpp')
        self.assert_(change.comments == 'Changes for changes sake\n')
        self.assert_(change.isdir == False)
        self.assert_(len(change.links) == 2)
        self.assert_(change.revision == '2010-08-11 04:56:44')
        dateTuple = parsedate_tz('Wed, 11 Aug 2010 04:56:44 +0000')
        self.assert_(change.when == mktime_tz(dateTuple))
        self.assert_(change.branch == None)
        self.assert_(change.revlink == '')
        self.assert_(change.repository == ':ext:cvshost.example.com:/cvsroot')
        self.assert_(change.project == 'MyModuleName')
