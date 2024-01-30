Added ability to poll HTTP event API of gerrit server to ``GerritChangeSource``. This is used
under following circumstances:
 - Any missed events are retrieved after Buildbot restart just like in ``GerritPollingChangeSource``.
 - Polling is used to detect any silent hang of underlying SSH connection when there are
   prolonged periods of inactivity (these may happen even when ServerAliveInterval is used)
