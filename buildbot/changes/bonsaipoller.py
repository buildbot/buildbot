
import time
from urllib import urlopen
from xml.dom import minidom, Node

from twisted.python import log, failure
from twisted.internet import defer, reactor
from twisted.internet.task import LoopingCall

from buildbot.changes import base, changes


class BonsaiResult:
    """I hold a list of CiNodes"""
    def __init__(self):
        self.nodes = []

class CiNode:
    """I hold information about one Ci node, including a list of files"""
    def __init__(self):
        self.log = ""
        self.who = ""
        self.date = ""
        self.files = []

class FileNode:
    """I hold information about one file node"""
    def __init__(self):
        self.revision = ""
        self.filename = ""

class BonsaiParser:
    """I parse the XML result from a Bonsai cvsquery.
    Typical usage is as follows::

     bp = BonsaiParser(urlopen(bonsaiURL))
     data = bp.getData()
     for cinode in data.nodes:
         print cinode.who, cinode.log, cinode.date
         for file in cinode.files:
             print file.filename, file.revision
    """

    def __init__(self, bonsaiQuery):
        try:
            self.dom = minidom.parse(bonsaiQuery)
        except:
            self.dom = None
            return
        self.currentCiNode = None
        self.currentFileNode = None

    def getData(self):
        """I return data from a Bonsai cvsquery"""
        data = BonsaiResult()
        while self._nextCiNode():
            ci = CiNode()
            ci.log = self._getLog()
            ci.who = self._getWho()
            ci.date = self._getDate()
            while self._nextFileNode():
                fn = FileNode()
                fn.revision = self._getRevision()
                fn.filename = self._getFilename()
                ci.files.append(fn)

            data.nodes.append(ci)

        return data


    def _nextCiNode(self):
        try:
            # first <ci> node?
            if not self.currentCiNode:
                # every other sibling is a <ci>, so jump 2 ahead
                self.currentCiNode = self.dom.getElementsByTagName("ci")[0]
            else:
                self.currentCiNode = self.currentCiNode.nextSibling.nextSibling
        except (AttributeError,IndexError):
            self.currentCiNode = None

        if self.currentCiNode:
            return True
        else:
            return False

    def _getLog(self):
        log = ""
        for child in self.currentCiNode.childNodes:
            if child.nodeType == Node.ELEMENT_NODE and child.tagName == "log":
                log = child.firstChild.data
        return str(log)


    def _getWho(self):
        """Returns the e-mail address of the commit'er"""
        return str(self.currentCiNode.getAttribute("who").replace("%", "@"))

    def _getDate(self):
        """Returns the date (unix time) of the commit"""
        return int(self.currentCiNode.getAttribute("date"))


    def _firstFileNode(self):
        for child in self.currentCiNode.childNodes:
            if child.nodeType == Node.ELEMENT_NODE and child.tagName == "files":
                # child is now the <files> element
                for c in child.childNodes:
                    if c.nodeType == Node.ELEMENT_NODE and c.tagName == "f":
                        return c

    def _nextFileNode(self):
        # every other sibling is a <f>, so go two past the current one
        try:
            # first <f> node?
            if not self.currentFileNode:
                self.currentFileNode = self._firstFileNode()
            else:
                self.currentFileNode = self.currentFileNode.nextSibling.nextSibling
        except AttributeError:
            self.currentFileNode = None

        if self.currentFileNode:
            return True
        else:
            return False

    def _getFilename(self):
        return str(self.currentFileNode.firstChild.data)

    def _getRevision(self):
        return str(self.currentFileNode.getAttribute("rev"))



class BonsaiPoller(base.ChangeSource):
    """This source will poll a bonsai server for changes and submit
    them to the change master."""

    compare_attrs = ["bonsaiURL", "pollInterval", "tree",
                     "module", "branch", "cvsroot"]

    parent = None # filled in when we're added
    loop = None
    volatile = ['loop']
    working = False

    def __init__(self, bonsaiURL, module, branch, tree="default",
                 cvsroot="/cvsroot", pollInterval=30):
        """
        @type   bonsaiURL:      string
        @param  bonsaiURL:      The base URL of the Bonsai server
                                (ie. http://bonsai.mozilla.org)
        @type   module:         string
        @param  module:         The module to look for changes in. Commonly
                                this is 'all'
        @type   branch:         string
        @param  branch:         The branch to look for changes in. This must
                                match the
                                'branch' option for the Scheduler.
        @type   tree:           string
        @param  tree:           The tree to look for changes in. Commonly this
                                is 'all'
        @type   cvsroot:        string
        @param  cvsroot:        The cvsroot of the repository. Usually this is
                                '/cvsroot'
        @type   pollInterval:   int
        @param  pollInterval:   The time (in seconds) between queries for changes
        """

        self.bonsaiURL = bonsaiURL
        self.module = module
        self.branch = branch
        self.tree = tree
        self.cvsroot = cvsroot
        self.pollInterval = pollInterval
        self.lastChange = time.time()
        self.lastPoll = time.time()

    def startService(self):
        self.loop = LoopingCall(self.poll)
        base.ChangeSource.startService(self)

        reactor.callLater(0, self.loop.start, self.pollInterval)

    def stopService(self):
        self.loop.stop()
        return base.ChangeSource.stopService(self)

    def describe(self):
        str = ""
        str += "Getting changes from the Bonsai service running at %s " \
                % self.bonsaiURL
        str += "<br>Using tree: %s, branch: %s, and module: %s" % (self.tree, \
                self.branch, self.module)
        return str

    def poll(self):
        if self.working:
            log.msg("Not polling Bonsai because last poll is still working")
        else:
            self.working = True
            d = self._get_changes()
            d.addCallback(self._process_changes)
            d.addBoth(self._finished)
        return

    def _finished(self, res):
        assert self.working
        self.working = False

        # check for failure
        if isinstance(res, failure.Failure):
            log.msg("Bonsai poll failed: %s" % res)
        return res

    def _get_changes(self):
        args = ["treeid=%s" % self.tree, "module=%s" % self.module,
                "branch=%s" % self.branch, "branchtype=match",
                "sortby=Date", "date=explicit",
                "mindate=%d" % self.lastChange,
                "maxdate=%d" % int(time.time()),
                "cvsroot=%s" % self.cvsroot, "xml=1"]
        # build the bonsai URL
        url = self.bonsaiURL
        url += "/cvsquery.cgi?"
        url += "&".join(args)
        log.msg("Polling Bonsai tree at %s" % url)

        self.lastPoll = time.time()
        # get the page, in XML format
        return defer.maybeDeferred(urlopen, url)

    def _process_changes(self, query):
        bp = BonsaiParser(query)
        files = []
        data = bp.getData()
        for cinode in data.nodes:
            for file in cinode.files:
                files.append(file.filename+' (revision '+file.revision+')')
            c = changes.Change(who = cinode.who,
                               files = files,
                               comments = cinode.log,
                               when = cinode.date,
                               branch = self.branch)
            self.parent.addChange(c)
            self.lastChange = self.lastPoll

