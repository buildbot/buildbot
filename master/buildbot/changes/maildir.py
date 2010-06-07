
# This is a class which watches a maildir for new messages. It uses the
# linux dirwatcher API (if available) to look for new files. The
# .messageReceived method is invoked with the filename of the new message,
# relative to the top of the maildir (so it will look like "new/blahblah").

import os
from twisted.python import log
from twisted.application import service, internet
from twisted.internet import reactor
dnotify = None
try:
    import dnotify
except:
    # I'm not actually sure this log message gets recorded
    log.msg("unable to import dnotify, so Maildir will use polling instead")

class NoSuchMaildir(Exception):
    pass

class MaildirService(service.MultiService):
    """I watch a maildir for new messages. I should be placed as the service
    child of some MultiService instance. When running, I use the linux
    dirwatcher API (if available) or poll for new files in the 'new'
    subdirectory of my maildir path. When I discover a new message, I invoke
    my .messageReceived() method with the short filename of the new message,
    so the full name of the new file can be obtained with
    os.path.join(maildir, 'new', filename). messageReceived() should be
    overridden by a subclass to do something useful. I will not move or
    delete the file on my own: the subclass's messageReceived() should
    probably do that.
    """
    pollinterval = 10  # only used if we don't have DNotify

    def __init__(self, basedir=None):
        """Create the Maildir watcher. BASEDIR is the maildir directory (the
        one which contains new/ and tmp/)
        """
        service.MultiService.__init__(self)
        self.basedir = basedir
        self.files = []
        self.dnotify = None

    def setBasedir(self, basedir):
        # some users of MaildirService (scheduler.Try_Jobdir, in particular)
        # don't know their basedir until setServiceParent, since it is
        # relative to the buildmaster's basedir. So let them set it late. We
        # don't actually need it until our own startService.
        self.basedir = basedir

    def startService(self):
        service.MultiService.startService(self)
        self.newdir = os.path.join(self.basedir, "new")
        if not os.path.isdir(self.basedir) or not os.path.isdir(self.newdir):
            raise NoSuchMaildir("invalid maildir '%s'" % self.basedir)
        try:
            if dnotify:
                # we must hold an fd open on the directory, so we can get
                # notified when it changes.
                self.dnotify = dnotify.DNotify(self.newdir,
                                               self.dnotify_callback,
                                               [dnotify.DNotify.DN_CREATE])
        except (IOError, OverflowError):
            # IOError is probably linux<2.4.19, which doesn't support
            # dnotify. OverflowError will occur on some 64-bit machines
            # because of a python bug
            log.msg("DNotify failed, falling back to polling")
        if not self.dnotify:
            t = internet.TimerService(self.pollinterval, self.poll)
            t.setServiceParent(self)
        self.poll()

    def dnotify_callback(self):
        log.msg("dnotify noticed something, now polling")

        # give it a moment. I found that qmail had problems when the message
        # was removed from the maildir instantly. It shouldn't, that's what
        # maildirs are made for. I wasn't able to eyeball any reason for the
        # problem, and safecat didn't behave the same way, but qmail reports
        # "Temporary_error_on_maildir_delivery" (qmail-local.c:165,
        # maildir_child() process exited with rc not in 0,2,3,4). Not sure
        # why, and I'd have to hack qmail to investigate further, so it's
        # easier to just wait a second before yanking the message out of new/

        reactor.callLater(0.1, self.poll)


    def stopService(self):
        if self.dnotify:
            self.dnotify.remove()
            self.dnotify = None
        return service.MultiService.stopService(self)

    def poll(self):
        assert self.basedir
        # see what's new
        for f in self.files:
            if not os.path.isfile(os.path.join(self.newdir, f)):
                self.files.remove(f)
        newfiles = []
        for f in os.listdir(self.newdir):
            if not f in self.files:
                newfiles.append(f)
        self.files.extend(newfiles)
        # TODO: sort by ctime, then filename, since safecat uses a rather
        # fine-grained timestamp in the filename
        for n in newfiles:
            # TODO: consider catching exceptions in messageReceived
            self.messageReceived(n)

    def messageReceived(self, filename):
        """Called when a new file is noticed. Will call
        self.parent.messageReceived() with a path relative to maildir/new.
        Should probably be overridden in subclasses."""
        self.parent.messageReceived(filename)

