import sys, os, time
from cPickle import dump

from zope.interface import implements
from twisted.python import log
from twisted.internet import defer
from twisted.application import service
from twisted.web import html

from buildbot import interfaces, util
from buildbot.process.properties import Properties

html_tmpl = """
<p>Changed by: <b>%(who)s</b><br />
Changed at: <b>%(at)s</b><br />
%(branch)s
%(revision)s
<br />

Changed files:
%(files)s

Comments:
%(comments)s

Properties:
%(properties)s
</p>
"""

class Change:
    """I represent a single change to the source tree. This may involve
    several files, but they are all changed by the same person, and there is
    a change comment for the group as a whole.

    If the version control system supports sequential repository- (or
    branch-) wide change numbers (like SVN, P4, and Arch), then revision=
    should be set to that number. The highest such number will be used at
    checkout time to get the correct set of files.

    If it does not (like CVS), when= should be set to the timestamp (seconds
    since epoch, as returned by time.time()) when the change was made. when=
    will be filled in for you (to the current time) if you omit it, which is
    suitable for ChangeSources which have no way of getting more accurate
    timestamps.

    Changes should be submitted to ChangeMaster.addChange() in
    chronologically increasing order. Out-of-order changes will probably
    cause the html.Waterfall display to be corrupted."""

    implements(interfaces.IStatusEvent)

    number = None

    branch = None
    category = None
    revision = None # used to create a source-stamp

    def __init__(self, who, files, comments, isdir=0, links=None,
                 revision=None, when=None, branch=None, category=None,
                 revlink='', properties={}):
        self.who = who
        self.comments = comments
        self.isdir = isdir
        if links is None:
            links = []
        self.links = links
        self.revision = revision
        if when is None:
            when = util.now()
        self.when = when
        self.branch = branch
        self.category = category
        self.revlink = revlink
        self.properties = Properties()
        self.properties.update(properties, "Change")

        # keep a sorted list of the files, for easier display
        self.files = files[:]
        self.files.sort()

    def __setstate__(self, dict):
        self.__dict__ = dict
        # Older Changes won't have a 'properties' attribute in them
        if not hasattr(self, 'properties'):
            self.properties = Properties()

    def asText(self):
        data = ""
        data += self.getFileContents()
        data += "At: %s\n" % self.getTime()
        data += "Changed By: %s\n" % self.who
        data += "Comments: %s" % self.comments
        data += "Properties: \n%s\n\n" % self.getProperties()
        return data

    def asHTML(self):
        links = []
        for file in self.files:
            link = filter(lambda s: s.find(file) != -1, self.links)
            if len(link) == 1:
                # could get confused
                links.append('<a href="%s"><b>%s</b></a>' % (link[0], file))
            else:
                links.append('<b>%s</b>' % file)
        if self.revision:
            if getattr(self, 'revlink', ""):
                revision = 'Revision: <a href="%s"><b>%s</b></a>\n' % (
                        self.revlink, self.revision)
            else:
                revision = "Revision: <b>%s</b><br />\n" % self.revision
        else:
            revision = ''

        branch = ""
        if self.branch:
            branch = "Branch: <b>%s</b><br />\n" % self.branch

        properties = []
        for prop in self.properties.asList():
            properties.append("%s: %s<br />" % (prop[0], prop[1]))

        kwargs = { 'who'       : html.escape(self.who),
                   'at'        : self.getTime(),
                   'files'     : html.UL(links) + '\n',
                   'revision'  : revision,
                   'branch'    : branch,
                   'comments'  : html.PRE(self.comments),
                   'properties': html.UL(properties) + '\n' }
        return html_tmpl % kwargs

    def get_HTML_box(self, url):
        """Return the contents of a TD cell for the waterfall display.

        @param url: the URL that points to an HTML page that will render
        using our asHTML method. The Change is free to use this or ignore it
        as it pleases.

        @return: the HTML that will be put inside the table cell. Typically
        this is just a single href named after the author of the change and
        pointing at the passed-in 'url'.
        """
        who = self.getShortAuthor()
        if self.comments is None:
            title = ""
        else:
            title = html.escape(self.comments)
        return '<a href="%s" title="%s">%s</a>' % (url,
                                                   title,
                                                   html.escape(who))

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

class ChangeMaster(service.MultiService):

    """This is the master-side service which receives file change
    notifications from CVS. It keeps a log of these changes, enough to
    provide for the HTML waterfall display, and to tell
    temporarily-disconnected bots what they missed while they were
    offline.

    Change notifications come from two different kinds of sources. The first
    is a PB service (servicename='changemaster', perspectivename='change'),
    which provides a remote method called 'addChange', which should be
    called with a dict that has keys 'filename' and 'comments'.

    The second is a list of objects derived from the ChangeSource class.
    These are added with .addSource(), which also sets the .changemaster
    attribute in the source to point at the ChangeMaster. When the
    application begins, these will be started with .start() . At shutdown
    time, they will be terminated with .stop() . They must be persistable.
    They are expected to call self.changemaster.addChange() with Change
    objects.

    There are several different variants of the second type of source:
    
      - L{buildbot.changes.mail.MaildirSource} watches a maildir for CVS
        commit mail. It uses DNotify if available, or polls every 10
        seconds if not.  It parses incoming mail to determine what files
        were changed.

      - L{buildbot.changes.freshcvs.FreshCVSSource} makes a PB
        connection to the CVSToys 'freshcvs' daemon and relays any
        changes it announces.
    
    """

    implements(interfaces.IEventSource)

    debug = False
    # todo: use Maildir class to watch for changes arriving by mail

    changeHorizon = 0

    def __init__(self):
        service.MultiService.__init__(self)
        self.changes = []
        # self.basedir must be filled in by the parent
        self.nextNumber = 1

    def addSource(self, source):
        assert interfaces.IChangeSource.providedBy(source)
        assert service.IService.providedBy(source)
        if self.debug:
            print "ChangeMaster.addSource", source
        source.setServiceParent(self)

    def removeSource(self, source):
        assert source in self
        if self.debug:
            print "ChangeMaster.removeSource", source, source.parent
        d = defer.maybeDeferred(source.disownServiceParent)
        return d

    def addChange(self, change):
        """Deliver a file change event. The event should be a Change object.
        This method will timestamp the object as it is received."""
        log.msg("adding change, who %s, %d files, rev=%s, branch=%s, "
                "comments %s, category %s" % (change.who, len(change.files),
                                              change.revision, change.branch,
                                              change.comments, change.category))
        change.number = self.nextNumber
        self.nextNumber += 1
        self.changes.append(change)
        self.parent.addChange(change)
        self.pruneChanges()

    def pruneChanges(self):
        if self.changeHorizon and len(self.changes) > self.changeHorizon:
            log.msg("pruning %i changes" % (len(self.changes) - self.changeHorizon))
            self.changes = self.changes[-self.changeHorizon:]

    def eventGenerator(self, branches=[], categories=[]):
        for i in range(len(self.changes)-1, -1, -1):
            c = self.changes[i]
            if (not branches or c.branch in branches) and (
                not categories or c.category in categories):
                yield c

    def getChangeNumbered(self, num):
        if not self.changes:
            return None
        first = self.changes[0].number
        if first + len(self.changes)-1 != self.changes[-1].number:
            log.msg(self,
                    "lost a change somewhere: [0] is %d, [%d] is %d" % \
                    (self.changes[0].number,
                     len(self.changes) - 1,
                     self.changes[-1].number))
            for c in self.changes:
                log.msg("c[%d]: " % c.number, c)
            return None
        offset = num - first
        log.msg(self, "offset", offset)
        if 0 <= offset <= len(self.changes):
            return self.changes[offset]
        else:
            return None

    def __getstate__(self):
        d = service.MultiService.__getstate__(self)
        del d['parent']
        del d['services'] # lose all children
        del d['namedServices']
        return d

    def __setstate__(self, d):
        self.__dict__ = d
        # self.basedir must be set by the parent
        self.services = [] # they'll be repopulated by readConfig
        self.namedServices = {}


    def saveYourself(self):
        filename = os.path.join(self.basedir, "changes.pck")
        tmpfilename = filename + ".tmp"
        try:
            dump(self, open(tmpfilename, "wb"))
            if sys.platform == 'win32':
                # windows cannot rename a file on top of an existing one
                if os.path.exists(filename):
                    os.unlink(filename)
            os.rename(tmpfilename, filename)
        except Exception, e:
            log.msg("unable to save changes")
            log.err()

    def stopService(self):
        self.saveYourself()
        return service.MultiService.stopService(self)

class TestChangeMaster(ChangeMaster):
    """A ChangeMaster for use in tests that does not save itself"""
    def stopService(self):
        return service.MultiService.stopService(self)
