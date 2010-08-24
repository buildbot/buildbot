import threading
import time

from twisted.python import log

class ThreadLeakMixin(object):
    """
    Monitor for leaking thread pools. Just call the setUp and tearDown methods!
    """
    def setUpThreadLeak(self):
        self.start_thdcount = len(threading.enumerate())

    def tearDownThreadLeak(self):
        # double-check we haven't left a ThreadPool open.  Sometimes, threads
        # take a while to go away, so this will wait up to 5s for that to occur
        for time in xrange(5):
            cur_thdcount = len(threading.enumerate())
            if cur_thdcount - self.start_thdcount < 1:
                return
            log.msg("threadcount: %d (start) %d (now)" % (self.start_thdcount, cur_thdcount))
            time.sleep(1)
        self.fail("leaked %d threads" % (cur_thdcount - self.start_thdcount))
