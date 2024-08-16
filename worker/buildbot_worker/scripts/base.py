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

# This module is left for backward compatibility of old-named worker API.
# It should never be imported by Buildbot.

import os


def isWorkerDir(dir):
    def print_error(error_message):
        print(f"{error_message}\ninvalid worker directory '{dir}'")

    buildbot_tac = os.path.join(dir, "buildbot.tac")
    try:
        with open(buildbot_tac) as f:
            contents = f.read()
    except OSError as exception:
        print_error(f"error reading '{buildbot_tac}': {exception.strerror}")
        return False

    if "Application('buildbot-worker')" not in contents:
        print_error(f"unexpected content in '{buildbot_tac}'")
        return False

    return True
