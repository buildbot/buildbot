# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members
#
# This code has originally been copied from cpython project.
#
# Copyright Python Software Foundation and contributors
# Licensed under Python Software Foundation License Version 2

import ntpath
import os
import posixpath


def posix_expanduser(path, worker_environ):
    """Expand ~ and ~user constructions.  If user or $HOME is unknown,
    do nothing."""
    path = os.fspath(path)
    tilde = "~"
    if not path.startswith(tilde):
        return path
    sep = posixpath._get_sep(path)
    i = path.find(sep, 1)
    if i < 0:
        i = len(path)
    if i == 1:
        if "HOME" not in worker_environ:
            try:
                import pwd
            except ImportError:
                # pwd module unavailable, return path unchanged
                return path
            try:
                userhome = pwd.getpwuid(os.getuid()).pw_dir
            except KeyError:
                # bpo-10496: if the current user identifier doesn't exist in the
                # password database, return the path unchanged
                return path
        else:
            userhome = worker_environ["HOME"]
    else:
        try:
            import pwd
        except ImportError:
            # pwd module unavailable, return path unchanged
            return path
        name = path[1:i]
        try:
            pwent = pwd.getpwnam(name)
        except KeyError:
            # bpo-10496: if the user name from the path doesn't exist in the
            # password database, return the path unchanged
            return path
        userhome = pwent.pw_dir
    root = "/"
    userhome = userhome.rstrip(root)
    return (userhome + path[i:]) or root


def nt_expanduser(path, worker_environ):
    """Expand ~ and ~user constructs.
    If user or $HOME is unknown, do nothing."""
    path = os.fspath(path)
    tilde = "~"
    if not path.startswith(tilde):
        return path
    i, n = 1, len(path)
    while i < n and path[i] not in ntpath._get_bothseps(path):
        i += 1

    if "USERPROFILE" in worker_environ:
        userhome = worker_environ["USERPROFILE"]
    elif "HOMEPATH" not in worker_environ:
        return path
    else:
        try:
            drive = worker_environ["HOMEDRIVE"]
        except KeyError:
            drive = ""
        userhome = ntpath.join(drive, worker_environ["HOMEPATH"])

    if i != 1:  # ~user
        target_user = path[1:i]
        current_user = worker_environ.get("USERNAME")

        if target_user != current_user:
            # Try to guess user home directory.  By default all user
            # profile directories are located in the same place and are
            # named by corresponding usernames.  If userhome isn't a
            # normal profile directory, this guess is likely wrong,
            # so we bail out.
            if current_user != ntpath.basename(userhome):
                return path
            userhome = ntpath.join(ntpath.dirname(userhome), target_user)

    return userhome + path[i:]
