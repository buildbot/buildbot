
import os, signal
from twisted.internet import reactor, task
from twisted.protocols.basic import LineOnlyReceiver

class FakeTransport:
    disconnecting = False

class LogWatcher(LineOnlyReceiver):
    POLL_INTERVAL = 0.1
    delimiter = "\n"

    def __init__(self, finished):
        self.poller = task.LoopingCall(self.poll)
        self.in_reconfig = False
        self.finished_cb = finished
        self.transport = FakeTransport()
        

    def start(self, logfile):
        try:
            self.f = open(logfile, "rb")
            self.f.seek(0, 2)
            self.poller.start(self.POLL_INTERVAL)
        except IOError:
            print "Unable to follow %s" % logfile
            return False
        return True

    def finished(self, success):
        self.in_reconfig = False
        self.finished_cb(success)

    def lineReceived(self, line):
        if "loading configuration from" in line:
            self.in_reconfig = True
        if self.in_reconfig:
            print line
        if "I will keep using the previous config file" in line:
            self.finished(False)
        if "configuration update complete" in line:
            self.finished(True)

    def poll(self):
        while True:
            data = self.f.read(1000)
            if not data:
                return
            self.dataReceived(data)

class Reconfigurator:
    def run(self, config):

        basedir = config['basedir']
        quiet = config['quiet']
        os.chdir(basedir)
        f = open("twistd.pid", "rt")
        pid = int(f.read().strip())
        if quiet:
            os.kill(pid, signal.SIGHUP)
            return
        # keep reading twistd.log. Display all messages between "loading
        # configuration from ..." and "configuration update complete" or
        # "I will keep using the previous config file instead.", or until
        # 5 seconds have elapsed.
        reactor.callLater(5, self.timeout)
        self.lw = lw = LogWatcher(self.finished)
        if lw.start("twistd.log"):
            # we're watching
            # give the LogWatcher a chance to start reading
            print "sending SIGHUP to process %d" % pid
            reactor.callLater(0.2, os.kill, pid, signal.SIGHUP)
            reactor.run()
        else:
            # we couldn't watch the file.. just SIGHUP it
            os.kill(pid, signal.SIGHUP)
            print "sent SIGHUP to process %d" % pid

    def finished(self, success):
        if success:
            print "Reconfiguration is complete."
        else:
            print "Reconfiguration failed."
        reactor.stop()

    def timeout(self):
        print "Never saw reconfiguration finish."
        reactor.stop()

def reconfig(config):
    r = Reconfigurator()
    r.run(config)

