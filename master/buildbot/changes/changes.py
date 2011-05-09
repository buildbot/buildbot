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

import os, time
from cPickle import dump

from zope.interface import implements
from twisted.python import log, runtime
from twisted.internet import defer
from twisted.web import html
from buildbot.util import datetime2epoch

from buildbot import interfaces, util
from buildbot.process.properties import Properties

class Change:
    """I represent a single change to the source tree. This may involve several
    files, but they are all changed by the same person, and there is a change
    comment for the group as a whole."""

    implements(interfaces.IStatusEvent)

    number = None
    branch = None
    category = None
    revision = None # used to create a source-stamp

    @classmethod
    def fromChdict(cls, master, chdict):
        """
        Class method to create a L{Change} from a dictionary as returned
        by L{ChangesConnectorComponent.getChange}.

        @param master: build master instance
        @param ssdict: change dictionary

        @returns: L{Change} via Deferred
        """
        change = cls(None, None, None, _fromChdict=True)
        change.who = chdict['author']
        change.comments = chdict['comments']
        change.isdir = chdict['is_dir']
        change.links = chdict['links']
        change.revision = chdict['revision']
        change.branch = chdict['branch']
        change.category = chdict['category']
        change.revlink = chdict['revlink']
        change.repository = chdict['repository']
        change.project = chdict['project']
        change.number = chdict['changeid']

        when = chdict['when_timestamp']
        if when:
            when = datetime2epoch(when)
        change.when = when

        change.files = chdict['files'][:]
        change.files.sort()

        change.properties = Properties()
        for n, (v,s) in chdict['properties'].iteritems():
            change.properties.setProperty(n, v, s)

        return defer.succeed(change)

    def __init__(self, who, files, comments, isdir=0, links=None,
                 revision=None, when=None, branch=None, category=None,
                 revlink='', properties={}, repository='', project='',
                 _fromChdict=False):
        # skip all this madness if we're being built from the database
        if _fromChdict:
            return

        self.who = who
        self.comments = comments
        self.isdir = isdir
        if links is None:
            links = []
        self.links = links

        def none_or_unicode(x):
            if x is None: return x
            return unicode(x)

        self.revision = none_or_unicode(revision)
        now = util.now()
        if when is None:
            self.when = now
        elif when > now:
            # this happens when the committing system has an incorrect clock, for example.
            # handle it gracefully
            log.msg("received a Change with when > now; assuming the change happened now")
            self.when = now
        else:
            self.when = when
        self.branch = none_or_unicode(branch)
        self.category = none_or_unicode(category)
        self.revlink = revlink
        self.properties = Properties()
        self.properties.update(properties, "Change")
        self.repository = repository
        self.project = project

        # keep a sorted list of the files, for easier display
        self.files = files[:]
        self.files.sort()

    def __setstate__(self, dict):
        self.__dict__ = dict
        # Older Changes won't have a 'properties' attribute in them
        if not hasattr(self, 'properties'):
            self.properties = Properties()
        if not hasattr(self, 'revlink'):
            self.revlink = ""

    def __str__(self):
        return (u"Change(who=%r, files=%r, comments=%r, revision=%r, " +
                u"when=%r, category=%r, project=%r, repository=%r)") % (
                self.who, self.files, self.comments, self.revision,
                self.when, self.category, self.project, self.repository)

    def asText(self):
        data = ""
        data += self.getFileContents()
        if self.repository:
            data += "On: %s\n" % self.repository
        if self.project:
            data += "For: %s\n" % self.project
        data += "At: %s\n" % self.getTime()
        data += "Changed By: %s\n" % self.who
        data += "Comments: %s" % self.comments
        data += "Properties: \n%s\n\n" % self.getProperties()
        return data

    def asDict(self):
        '''returns a dictonary with suitable info for html/mail rendering'''
        result = {}

        files = []
        for file in self.files:
            link = filter(lambda s: s.find(file) != -1, self.links)
            if len(link) == 1:
                url = link[0]
            else:
                url = None
            files.append(dict(url=url, name=file))

        files = sorted(files, cmp=lambda a, b: a['name'] < b['name'])

        # Constant
        result['number'] = self.number
        result['branch'] = self.branch
        result['category'] = self.category
        result['who'] = self.getShortAuthor()
        result['comments'] = self.comments
        result['revision'] = self.revision
        result['rev'] = self.revision
        result['when'] = self.when
        result['at'] = self.getTime()
        result['files'] = files
        result['revlink'] = getattr(self, 'revlink', None)
        result['properties'] = self.properties.asList()
        result['repository'] = getattr(self, 'repository', None)
        result['project'] = getattr(self, 'project', None)
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

    def getFileContents(self):
        data = ""
        if len(self.files) == 1:
            if self.isdir:
                data += "Directory: %s\n" % self.files[0]
            else:
                data += "File: %s\n" % self.files[0]
        else:
            data += "Files:\n"
            for f in self.files:
                data += " %s\n" % f
        return data

    def getProperties(self):
        data = ""
        for prop in self.properties.asList():
            data += "  %s: %s" % (prop[0], prop[1])
        return data


class ChangeMaster: # pragma: no cover
    # this is a stub, retained to allow the "buildbot upgrade-master" tool to
    # read old changes.pck pickle files and convert their contents into the
    # new database format. This is only instantiated by that tool, or by
    # test_db.py which tests that tool. The functionality that previously
    # lived here has been moved into buildbot.changes.manager.ChangeManager

    def __init__(self):
        self.changes = []
        # self.basedir must be filled in by the parent
        self.nextNumber = 1

    def saveYourself(self):
        filename = os.path.join(self.basedir, "changes.pck")
        tmpfilename = filename + ".tmp"
        try:
            dump(self, open(tmpfilename, "wb"))
            if runtime.platformType  == 'win32':
                # windows cannot rename a file on top of an existing one
                if os.path.exists(filename):
                    os.unlink(filename)
            os.rename(tmpfilename, filename)
        except Exception:
            log.msg("unable to save changes")
            log.err()

    # This method is used by contrib/fix_changes_pickle_encoding.py to recode all
    # bytestrings in an old changes.pck into unicode strings
    def recode_changes(self, old_encoding, quiet=False):
        """Processes the list of changes, with the change attributes re-encoded
        unicode objects"""
        nconvert = 0
        for c in self.changes:
            # give revision special handling, in case it is an integer
            if isinstance(c.revision, int):
                c.revision = unicode(c.revision)

            for attr in ("who", "comments", "revlink", "category", "branch", "revision"):
                a = getattr(c, attr)
                if isinstance(a, str):
                    try:
                        setattr(c, attr, a.decode(old_encoding))
                        nconvert += 1
                    except UnicodeDecodeError:
                        raise UnicodeError("Error decoding %s of change #%s as %s:\n%r" %
                                        (attr, c.number, old_encoding, a))

            # filenames are a special case, but in general they'll have the same encoding
            # as everything else on a system.  If not, well, hack this script to do your
            # import!
            newfiles = []
            for filename in util.flatten(c.files):
                if isinstance(filename, str):
                    try:
                        filename = filename.decode(old_encoding)
                        nconvert += 1
                    except UnicodeDecodeError:
                        raise UnicodeError("Error decoding filename '%s' of change #%s as %s:\n%r" %
                                        (filename.decode('ascii', 'replace'),
                                         c.number, old_encoding, a))
                newfiles.append(filename)
            c.files = newfiles
        if not quiet:
            print "converted %d strings" % nconvert

class OldChangeMaster(ChangeMaster): # pragma: no cover
    # this is a reminder that the ChangeMaster class is old
    pass
# vim: set ts=4 sts=4 sw=4 et:
