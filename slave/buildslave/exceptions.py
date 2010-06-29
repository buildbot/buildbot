class AbandonChain(Exception):
    """A series of chained steps can raise this exception to indicate that
    one of the intermediate RunProcesses has failed, such that there is no
    point in running the remainder. 'rc' should be the non-zero exit code of
    the failing ShellCommand."""

    def __repr__(self):
        return "<AbandonChain rc=%s>" % self.args[0]
