import logging

from twisted.python import log


class Logger(object):
    """This is a minimal compatibility shim, rather than a backport.

    For now we'd like to avoid backporting the whole of ``twisted.logger``,
    as is seem disproportionate to the actual need we have for it, but it
    could be done in the future.

    Currently, this is used in the ``ClientService`` backport only.

    Level can get copied in the emitted messages, to distinguish info/warning,
    because the legacy ``log`` module does not have a ``warn()`` function.
    They also get forwarded in kwargs, similar as what ``twisted.logger`` would
    do, giving observers a chance to treat them accordingly.
    """

    def info(self, fmt=None, **kw):
        if fmt is not None and kw:
            msg = fmt.format(**kw)
        log.msg(msg, log_level=logging.INFO, **kw)

    def warn(self, fmt=None, **kw):
        if fmt is not None and kw:
            msg = fmt.format(**kw)
        log.msg('WARNING ' + msg, log_level=logging.WARNING, **kw)
