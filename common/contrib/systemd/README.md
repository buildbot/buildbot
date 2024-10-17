# Common files for buildbot systemd services

These files are for creating system users and data directory for buildbot systemd services (`master/contrib/systemd/buildbot@.service` and `worker/contrib/systemd/buildbot-worker@.service`).

## Usage

```
$ sudo install -Dm644 ./sysusers.d/buildbot.conf /usr/lib/sysusers.d/buildbot.conf
$ sudo install -Dm644 ./tmpfiles.d/buildbot.conf /usr/lib/tmpfiles.d/buildbot.conf
$ sudo /usr/bin/systemd-sysusers
$ sudo /usr/bin/systemd-tmpfiles --create
```

Packagers may place the last two commands into package post-installation scripts if those are not already in transaction scripts (e.g., dpkg triggers for Debian-based systems or ALPM hooks for Arch-based systems).
