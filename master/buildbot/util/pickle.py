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

import cPickle
import cStringIO
import new
import os
import sys

from buildbot import interfaces
from buildbot import util
from twisted.internet import defer
from twisted.internet import reactor
from twisted.persisted import styles
from twisted.python import log
from twisted.python import reflect
from twisted.python import runtime
from zope.interface import implements

# This module contains classes that are referenced in pickles, and thus needed
# during upgrade operations, but are no longer used in a running Buildbot
# master.
substituteClasses = {}


class SourceStamp(styles.Versioned):  # pragma: no cover
    persistenceVersion = 3
    persistenceForgets = ('wasUpgraded', )

    # all seven of these are publicly visible attributes
    branch = None
    revision = None
    patch = None
    patch_info = None
    changes = ()
    project = ''
    repository = ''
    codebase = ''
    sourcestampsetid = None
    ssid = None

    compare_attrs = ('branch', 'revision', 'patch', 'patch_info', 'changes', 'project', 'repository', 'codebase')

    implements(interfaces.ISourceStamp)

    def __init__(self, branch=None, revision=None, patch=None,
                 patch_info=None, changes=None, project='', repository='',
                 codebase='', _ignoreChanges=False):

        if patch is not None:
            assert 2 <= len(patch) <= 3
            assert int(patch[0]) != -1
        self.branch = branch
        self.patch = patch
        self.patch_info = patch_info
        self.project = project or ''
        self.repository = repository or ''
        self.codebase = codebase or ''
        if changes:
            self.changes = changes = list(changes)
            changes.sort()
            if not _ignoreChanges:
                # set branch and revision to most recent change
                self.branch = changes[-1].branch
                revision = changes[-1].revision
                if not self.project and hasattr(changes[-1], 'project'):
                    self.project = changes[-1].project
                if not self.repository and hasattr(changes[-1], 'repository'):
                    self.repository = changes[-1].repository

        if revision is not None:
            if isinstance(revision, int):
                revision = str(revision)

        self.revision = revision

    def upgradeToVersion1(self):
        # version 0 was untyped; in version 1 and later, types matter.
        if self.branch is not None and not isinstance(self.branch, str):
            self.branch = str(self.branch)
        if self.revision is not None and not isinstance(self.revision, str):
            self.revision = str(self.revision)
        if self.patch is not None:
            self.patch = (int(self.patch[0]), str(self.patch[1]))
        self.wasUpgraded = True

    def upgradeToVersion2(self):
        # version 1 did not have project or repository; just set them to a default ''
        self.project = ''
        self.repository = ''
        self.wasUpgraded = True

    def upgradeToVersion3(self):
        # The database has been upgraded where all existing sourcestamps got an
        # setid equal to its ssid
        self.sourcestampsetid = self.ssid
        # version 2 did not have codebase; set to ''
        self.codebase = ''
        self.wasUpgraded = True
substituteClasses['buildbot.sourcestamp', 'SourceStamp'] = SourceStamp


class ChangeMaster:  # pragma: no cover

    def __init__(self):
        self.changes = []
        # self.basedir must be filled in by the parent
        self.nextNumber = 1

    def saveYourself(self):
        filename = os.path.join(self.basedir, "changes.pck")
        tmpfilename = filename + ".tmp"
        try:
            with open(tmpfilename, "wb") as f:
                dump(self, f)
            if runtime.platformType == 'win32':
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
substituteClasses['buildbot.changes.changes', 'ChangeMaster'] = ChangeMaster


class BuildStepStatus(styles.Versioned):

    persistenceVersion = 4
    persistenceForgets = ('wasUpgraded', )

    started = None
    finished = None
    progress = None
    text = []
    results = None
    text2 = []
    watchers = []
    updates = {}
    finishedWatchers = []
    step_number = None
    hidden = False

    def __init__(self, parent, master, step_number):
        assert interfaces.IBuildStatus(parent)
        self.build = parent
        self.step_number = step_number
        self.hidden = False
        self.logs = []
        self.urls = {}
        self.watchers = []
        self.updates = {}
        self.finishedWatchers = []
        self.skipped = False

        self.master = master

        self.waitingForLocks = False

    def getName(self):
        """Returns a short string with the name of this step. This string
        may have spaces in it."""
        return self.name

    def getBuild(self):
        return self.build

    def getTimes(self):
        return (self.started, self.finished)

    def getExpectations(self):
        """Returns a list of tuples (name, current, target)."""
        if not self.progress:
            return []
        ret = []
        metrics = sorted(self.progress.progress.keys())
        for m in metrics:
            t = (m, self.progress.progress[m], self.progress.expectations[m])
            ret.append(t)
        return ret

    def getLogs(self):
        return self.logs

    def getURLs(self):
        return self.urls.copy()

    def isStarted(self):
        return (self.started is not None)

    def isSkipped(self):
        return self.skipped

    def isFinished(self):
        return (self.finished is not None)

    def isHidden(self):
        return self.hidden

    def waitUntilFinished(self):
        if self.finished:
            d = defer.succeed(self)
        else:
            d = defer.Deferred()
            self.finishedWatchers.append(d)
        return d

    # while the step is running, the following methods make sense.
    # Afterwards they return None

    def getETA(self):
        if self.started is None:
            return None  # not started yet
        if self.finished is not None:
            return None  # already finished
        if not self.progress:
            return None  # no way to predict
        return self.progress.remaining()

    # Once you know the step has finished, the following methods are legal.
    # Before this step has finished, they all return None.

    def getText(self):
        """Returns a list of strings which describe the step. These are
        intended to be displayed in a narrow column. If more space is
        available, the caller should join them together with spaces before
        presenting them to the user."""
        return self.text

    def getResults(self):
        """Return a tuple describing the results of the step.
        'result' is one of the constants in L{buildbot.status.builder}:
        SUCCESS, WARNINGS, FAILURE, or SKIPPED.
        'strings' is an optional list of strings that the step wants to
        append to the overall build's results. These strings are usually
        more terse than the ones returned by getText(): in particular,
        successful Steps do not usually contribute any text to the
        overall build.

        @rtype:   tuple of int, list of strings
        @returns: (result, strings)
        """
        return (self.results, self.text2)

    # subscription interface

    def subscribe(self, receiver, updateInterval=10):
        # will get logStarted, logFinished, stepETAUpdate
        assert receiver not in self.watchers
        self.watchers.append(receiver)
        self.sendETAUpdate(receiver, updateInterval)

    def sendETAUpdate(self, receiver, updateInterval):
        self.updates[receiver] = None
        # they might unsubscribe during stepETAUpdate
        receiver.stepETAUpdate(self.build, self,
                               self.getETA(), self.getExpectations())
        if receiver in self.watchers:
            self.updates[receiver] = reactor.callLater(updateInterval,
                                                       self.sendETAUpdate,
                                                       receiver,
                                                       updateInterval)

    def unsubscribe(self, receiver):
        if receiver in self.watchers:
            self.watchers.remove(receiver)
        if receiver in self.updates:
            if self.updates[receiver] is not None:
                self.updates[receiver].cancel()
            del self.updates[receiver]

    # Note: setter methods have been removed

    def checkLogfiles(self):
        # filter out logs that have been deleted
        self.logs = [l for l in self.logs if l.old_hasContents()]

    # persistence

    def __getstate__(self):
        d = styles.Versioned.__getstate__(self)
        del d['build']  # filled in when loading
        if "progress" in d:
            del d['progress']
        del d['watchers']
        del d['finishedWatchers']
        del d['updates']
        del d['master']

        for attr in ("getStatistic", "hasStatistic", "setStatistic"):
            if attr in d:
                del d[attr]

        return d

    def __setstate__(self, d):
        styles.Versioned.__setstate__(self, d)
        # self.build must be filled in by our parent

        # point the logs to this object
        self.watchers = []
        self.finishedWatchers = []
        self.updates = {}

    def setProcessObjects(self, build, master):
        self.build = build
        self.master = master
        for loog in self.logs:
            loog.step = self
            loog.master = master

    def upgradeToVersion1(self):
        if not hasattr(self, "urls"):
            self.urls = {}
        self.wasUpgraded = True

    def upgradeToVersion2(self):
        if not hasattr(self, "statistics"):
            self.statistics = {}
        self.wasUpgraded = True

    def upgradeToVersion3(self):
        if not hasattr(self, "step_number"):
            self.step_number = 0
        self.wasUpgraded = True

    def upgradeToVersion4(self):
        if not hasattr(self, "hidden"):
            self.hidden = False
        self.wasUpgraded = True

    def asDict(self):
        result = {}
        # Constant
        result['name'] = self.getName()

        # Transient
        result['text'] = self.getText()
        result['results'] = self.getResults()
        result['isStarted'] = self.isStarted()
        result['isFinished'] = self.isFinished()
        result['times'] = self.getTimes()
        result['expectations'] = self.getExpectations()
        result['eta'] = self.getETA()
        result['urls'] = self.getURLs()
        result['step_number'] = self.step_number
        result['hidden'] = self.hidden
        result['logs'] = [[l.getName(), None]  # used to be (name, URL)
                          for l in self.getLogs()]
        return result
# styles.Versioned requires this latter, as it keys the version numbers on the
# fully qualified class name.  This module appeared in two different modules
# historically
BuildStepStatus.__module__ = 'buildbot.status.builder'
substituteClasses['buildbot.status.buildstep', 'BuildStepStatus'] = BuildStepStatus
substituteClasses['buildbot.status.builder', 'BuildStepStatus'] = BuildStepStatus

_already_setup = False


def setup():
    global _already_setup
    if _already_setup:
        return

    # move each of the substitute classes to its proper module in sys.modules,
    # creating it if necessary, and set its __module__ attribute.
    for info, cls in substituteClasses.iteritems():
        mod_name, cls_name = info
        try:
            mod = reflect.namedModule(mod_name)
        except (ImportError, AttributeError):
            mod = new.module(mod_name)
            sys.modules[mod_name] = mod
        setattr(mod, cls_name, cls)

    _already_setup = True

# replacements for stdlib pickle methods


def _makeUnpickler(file):
    setup()
    up = cPickle.Unpickler(file)
    # see http://docs.python.org/2/library/pickle.html#subclassing-unpicklers

    def find_global(modname, clsname):
        try:
            return substituteClasses[(modname, clsname)]
        except KeyError:
            mod = reflect.namedModule(modname)
            try:
                return getattr(mod, clsname)
            except AttributeError:
                raise AttributeError("Module %r (%s) has no attribute %s"
                                     % (mod, modname, clsname))
    up.find_global = find_global
    return up


def load(file):
    return _makeUnpickler(file).load()


def loads(str):
    file = cStringIO.StringIO(str)
    return _makeUnpickler(file).load()

dump = cPickle.dump
dumps = cPickle.dumps
