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
from future.utils import iteritems
from future.utils import text_type

import html  # py2: via future
import time

from twisted.internet import defer
from twisted.python import log
from zope.interface import implementer

from buildbot import interfaces
from buildbot import util
from buildbot.process.properties import Properties
from buildbot.util import datetime2epoch


@implementer(interfaces.IStatusEvent)
class Change:

    """I represent a single change to the source tree. This may involve several
    files, but they are all changed by the same person, and there is a change
    comment for the group as a whole."""

    number = None
    branch = None
    category = None
    revision = None  # used to create a source-stamp
    links = []  # links are gone, but upgrade code expects this attribute

    @classmethod
    def fromChdict(cls, master, chdict):
        """
        Class method to create a L{Change} from a dictionary as returned
        by L{ChangesConnectorComponent.getChange}.

        @param master: build master instance
        @param ssdict: change dictionary

        @returns: L{Change} via Deferred
        """
        cache = master.caches.get_cache("Changes", cls._make_ch)
        return cache.get(chdict['changeid'], chdict=chdict, master=master)

    @classmethod
    def _make_ch(cls, changeid, master, chdict):
        change = cls(None, None, None, _fromChdict=True)
        change.who = chdict['author']
        change.comments = chdict['comments']
        change.revision = chdict['revision']
        change.branch = chdict['branch']
        change.category = chdict['category']
        change.revlink = chdict['revlink']
        change.repository = chdict['repository']
        change.codebase = chdict['codebase']
        change.project = chdict['project']
        change.number = chdict['changeid']

        when = chdict['when_timestamp']
        if when:
            when = datetime2epoch(when)
        change.when = when

        change.files = sorted(chdict['files'])

        change.properties = Properties()
        for n, (v, s) in iteritems(chdict['properties']):
            change.properties.setProperty(n, v, s)

        return defer.succeed(change)

    def __init__(self, who, files, comments, revision=None, when=None,
                 branch=None, category=None, revlink='', properties=None,
                 repository='', codebase='', project='', _fromChdict=False):
        if properties is None:
            properties = {}
        # skip all this madness if we're being built from the database
        if _fromChdict:
            return

        self.who = who
        self.comments = comments

        def none_or_unicode(x):
            if x is None:
                return x
            return text_type(x)

        self.revision = none_or_unicode(revision)
        now = util.now()
        if when is None:
            self.when = now
        elif when > now:
            # this happens when the committing system has an incorrect clock, for example.
            # handle it gracefully
            log.msg(
                "received a Change with when > now; assuming the change happened now")
            self.when = now
        else:
            self.when = when
        self.branch = none_or_unicode(branch)
        self.category = none_or_unicode(category)
        self.revlink = revlink
        self.properties = Properties()
        self.properties.update(properties, "Change")
        self.repository = repository
        self.codebase = codebase
        self.project = project

        # keep a sorted list of the files, for easier display
        self.files = sorted(files or [])

    def __setstate__(self, dict):
        self.__dict__ = dict
        # Older Changes won't have a 'properties' attribute in them
        if not hasattr(self, 'properties'):
            self.properties = Properties()
        if not hasattr(self, 'revlink'):
            self.revlink = ""

    def __str__(self):
        return (u"Change(revision=%r, who=%r, branch=%r, comments=%r, " +
                u"when=%r, category=%r, project=%r, repository=%r, " +
                u"codebase=%r)") % (
            self.revision, self.who, self.branch, self.comments,
            self.when, self.category, self.project, self.repository,
            self.codebase)

    def __eq__(self, other):
        return self.number == other.number

    def __ne__(self, other):
        return self.number != other.number

    def __lt__(self, other):
        return self.number < other.number

    def __le__(self, other):
        return self.number <= other.number

    def __gt__(self, other):
        return self.number > other.number

    def __ge__(self, other):
        return self.number >= other.number

    def asText(self):
        data = ""
        data += "Files:\n"
        for f in self.files:
            data += " %s\n" % f
        if self.repository:
            data += "On: %s\n" % self.repository
        if self.project:
            data += "For: %s\n" % self.project
        data += "At: %s\n" % self.getTime()
        data += "Changed By: %s\n" % self.who
        data += "Comments: %s" % self.comments
        data += "Properties: \n"
        for prop in self.properties.asList():
            data += "  %s: %s" % (prop[0], prop[1])
        data += '\n\n'
        return data

    def asDict(self):
        '''returns a dictionary with suitable info for html/mail rendering'''
        files = [dict(name=f) for f in self.files]
        files.sort(key=lambda a: a['name'])

        result = {
            # Constant
            'number': self.number,
            'branch': self.branch,
            'category': self.category,
            'who': self.getShortAuthor(),
            'comments': self.comments,
            'revision': self.revision,
            'rev': self.revision,
            'when': self.when,
            'at': self.getTime(),
            'files': files,
            'revlink': getattr(self, 'revlink', None),
            'properties': self.properties.asList(),
            'repository': getattr(self, 'repository', None),
            'codebase': getattr(self, 'codebase', ''),
            'project': getattr(self, 'project', None)
        }
        return result

    def getShortAuthor(self):
        return self.who

    def getTime(self):
        if not self.when:
            return "?"
        return time.strftime("%a %d %b %Y %H:%M:%S",
                             time.localtime(self.when))

    def getTimes(self):
        return (self.when, None)

    def getText(self):
        return [html.escape(self.who)]

    def getLogs(self):
        return {}
