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

import re

ANSI_RE = re.compile(r"^((\d+)(;\d+)*)?([a-zA-Z])")


def parse_ansi_sgr(ansi_entry):
    """simple utility to extract ansi sgr (Select Graphic Rendition) codes,
    and ignore other codes.
    Invalid codes are restored
    """
    classes = []
    res = ANSI_RE.search(ansi_entry)
    if res:
        mode = res.group(4)
        ansi_entry = ansi_entry[len(res.group(0)):]
        if mode == 'm':
            classes = res.group(1)
            if classes:
                classes = res.group(1).split(";")
            else:
                classes = []
    else:
        # illegal code, restore the CSI
        ansi_entry = "\033[" + ansi_entry
    return ansi_entry, classes
