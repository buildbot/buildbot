#!/usr/bin/python


import re
import sys

spaces = re.compile("^ +")
for fn in sys.argv[1:]:
    lines = []
    with open(fn, 'r') as f:
        for line in f:
            lines.append(line)

    def getIndent(i):
        res = spaces.match(lines[i])
        if res is None:
            return 0
        return len(res.group(0))

    def IndentBlock(i, numspaces):
        initIndent = getIndent(i)
        while i < len(lines) and initIndent <= getIndent(i):
            lines[i] = " " * numspaces + lines[i]
            i += 1

    for i, line in enumerate(lines):
        missingIndent = 4 - (getIndent(i) % 4)
        if missingIndent != 4:
            IndentBlock(i, missingIndent)

    with open(fn, 'w') as f:
        for line in lines:
            f.write(line)
