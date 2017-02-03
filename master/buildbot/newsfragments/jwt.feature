Buildbot now uses `JWT <https://en.wikipedia.org/wiki/JSON_Web_Token>`_ to store its web UI Sessions.
Sessions now persist upon buildbot restart.
Sessions are shared between masters.
Session expiration time is configurable with ``c['www']['cookie_expiration_time']`` see :bb:cfg:`www`.
