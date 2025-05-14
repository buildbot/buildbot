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

from __future__ import annotations

import os
import re
from typing import Mapping

_ENV_VAR_PATTERN = re.compile(r'\${([0-9a-zA-Z_]*)}')


def compute_environ(
    environ: Mapping[str, str | list[str] | None] | None,
    os_environ: Mapping[str, str],
    pathsep: str = os.pathsep,
) -> dict[str, str]:
    new_environ = {k: v for k, v in os_environ.items()}
    if not environ:
        return new_environ

    def subst(match: re.Match[str]) -> str:
        return os_environ.get(match.group(1), "")

    for key, value in environ.items():
        if value is None:
            # setting a key to None will delete it from the worker
            # environment
            new_environ.pop(key, None)
            continue

        if isinstance(value, list):
            # Need to do os.pathsep translation.  We could either do that
            # by replacing all incoming ':'s with os.pathsep, or by
            # accepting lists.  I like lists better.
            # If it's not a string, treat it as a sequence to be
            # turned in to a string.
            value = pathsep.join(value)

        if not isinstance(value, str):
            raise RuntimeError(f"'env' values must be strings or lists; key '{key}' is incorrect")
        # substitute ${name} patterns with envvar value
        new_environ[key] = _ENV_VAR_PATTERN.sub(subst, value)

    # Special case for PYTHONPATH
    # If overriden, make sure it's still present
    if "PYTHONPATH" in environ:
        new_environ['PYTHONPATH'] += pathsep + os_environ.get("PYTHONPATH", "")

    return new_environ
