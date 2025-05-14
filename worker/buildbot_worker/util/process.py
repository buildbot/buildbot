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


def compute_environ(
    environ: dict[str, str | list[str] | int | None] | None = None,
) -> dict[str, str]:
    if environ:
        for key, v in environ.items():
            if isinstance(v, list):
                # Need to do os.pathsep translation.  We could either do that
                # by replacing all incoming ':'s with os.pathsep, or by
                # accepting lists.  I like lists better.
                # If it's not a string, treat it as a sequence to be
                # turned in to a string.

                # TODO: replace `os.pathsep.join(environ[key])` -> `os.pathsep.join(v)`
                environ[key] = os.pathsep.join(environ[key])  # type: ignore[arg-type]

        if "PYTHONPATH" in environ:
            environ['PYTHONPATH'] += os.pathsep + "${PYTHONPATH}"  # type: ignore[operator]

        # do substitution on variable values matching pattern: ${name}
        p = re.compile(r'\${([0-9a-zA-Z_]*)}')

        def subst(match: re.Match[str]) -> str:
            return os.environ.get(match.group(1), "")

        newenv = {}
        for key in os.environ:
            # setting a key to None will delete it from the worker
            # environment
            if key not in environ or environ[key] is not None:
                newenv[key] = os.environ[key]
        for key, v in environ.items():
            if v is not None:
                if not isinstance(v, str):
                    raise RuntimeError(
                        f"'env' values must be strings or lists; key '{key}' is incorrect"
                    )
                newenv[key] = p.sub(subst, v)

        return newenv
    else:  # not environ
        return os.environ.copy()
