# Common files for buildbot systemd services

These files create the system user and data directory used by the buildbot
systemd template units (`master/contrib/systemd/buildbot@.service` and
`worker/contrib/systemd/buildbot-worker@.service`).

- `sysusers.d/buildbot.conf` -- creates the `buildbot` system user
- `tmpfiles.d/buildbot.conf` -- creates `/var/lib/buildbot` owned by `buildbot`

The units set `StateDirectory=buildbot`, which also creates `/var/lib/buildbot`
at service start as a runtime fallback if tmpfiles.d has not been applied.

## Setup

```
# 1. Install sysusers.d and tmpfiles.d configs, then apply them
$ sudo install -Dm644 ./sysusers.d/buildbot.conf /usr/lib/sysusers.d/buildbot.conf
$ sudo install -Dm644 ./tmpfiles.d/buildbot.conf /usr/lib/tmpfiles.d/buildbot.conf
$ sudo systemd-sysusers
$ sudo systemd-tmpfiles --create

# 2. Install the systemd unit(s) you need
$ sudo install -Dm644 master/contrib/systemd/buildbot@.service /usr/lib/systemd/system/buildbot@.service
$ sudo install -Dm644 worker/contrib/systemd/buildbot-worker@.service /usr/lib/systemd/system/buildbot-worker@.service
$ sudo systemctl daemon-reload

# 3. Create a master or worker instance
$ cd /var/lib/buildbot
$ sudo -u buildbot buildbot create-master <name>
# or
$ sudo -u buildbot buildbot-worker create-worker <name> <master-hostname> <name> <password>

# 4. Enable and start
$ sudo systemctl enable --now buildbot@<name>.service
# or
$ sudo systemctl enable --now buildbot-worker@<name>.service
```

Packagers may place the sysusers/tmpfiles commands into package
post-installation scripts if those are not already handled by transaction
scripts (e.g., dpkg triggers for Debian-based systems or ALPM hooks for
Arch-based systems).
