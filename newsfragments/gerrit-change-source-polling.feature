Added ability to poll HTTP event API of Gerrit server to ``GerritChangeSource``. This has the
following advantages compared to simply pointing ``GerritChangeSource`` and
``GerritEventLogPoller`` at the same Gerrit server:

 - All events are properly deduplicated
 - SSH connection is restarted in case of silent hangs of underlying SSH connection (this may
   happen even when ServerAliveInterval is used)
