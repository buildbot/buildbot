# coding=utf-8
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

from twisted.spread import pb
from twisted.python import log

def patch():
    log.msg("Applying patch for http://twistedmatrix.com/trac/ticket/4520")
    pb.RemoteError = RemoteError
    pb.CopiedFailure.throwExceptionIntoGenerator = \
       CopiedFailure_throwExceptionIntoGenerator
    old_getStateToCopy = pb.CopyableFailure.getStateToCopy
    def getStateToCopy(self):
        state = old_getStateToCopy(self)
        state['value'] = str(self.value) # Exception instance
        return state


#############################################################################
# Everything below this line was taken from Twisted, except as annotated.  See
# http://twistedmatrix.com/trac/changeset/32211
#
# Merge copiedfailure-stringexc-4520
#
# Author: sirgolan, Koblaid, glyph
# Reviewer: exarkun, glyph
# Fixes: #4520
#
#    Allow inlineCallbacks and exceptions raised from a twisted.spread remote
#    call to work together. A new RemoteError exception will be raised into
#    the generator when a yielded Deferred fails with a remote PB failure.

class RemoteError(Exception):
    def __init__(self, remoteType, value, remoteTraceback):
        Exception.__init__(self, value)
        self.remoteType = remoteType
        self.remoteTraceback = remoteTraceback

def CopiedFailure_throwExceptionIntoGenerator(self, g):
    return g.throw(RemoteError(self.type, self.value, self.traceback)) 
