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
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # NOTE: can't use newer `|` annotations for TypedDict def
    from typing import Optional
    from typing import Union

    from typing_extensions import Literal
    from typing_extensions import TypedDict

    # Use alternative synthax due to some fields containing non-valid indentifier chars (eg. '-')
    Options = TypedDict(
        "Options",
        {
            # flags
            "no-logrotate": bool,
            "relocatable": bool,
            "quiet": bool,
            "use-tls": bool,
            "delete-leftover-dirs": bool,
            # options
            "basedir": str,
            "allow-shutdown": Optional[Literal["signal"]],
            "umask": Union[int, str, None],
            "log-size": int,
            "log-count": Union[int, str],
            "keepalive": int,
            "maxdelay": int,
            "numcpus": Union[int, str, None],
            "protocol": Literal["pb", "msgpack", "null"],
            "maxretries": Union[int, str, None],
            "connection-string": Union[str, None],
            "proxy-connection-string": Union[str, None],
            # arguments
            "host": Union[str, None],
            "port": Union[int, None],
            "name": str,
            "passwd": str,
        },
    )


def isWorkerDir(dir: str) -> bool:
    def print_error(error_message: str) -> None:
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
