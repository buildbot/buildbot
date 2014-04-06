#!/usr/bin/env python
#
# Copyright 2008
# Steve 'Ashcrow' Milner <smilner+buildbot@redhat.com>
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
"""
Generates changelog information using git.
"""

__docformat__ = 'restructuredtext'


import os
import sys


def print_err(msg):
    """
    Wrapper to make printing to stderr nicer.

    :Parameters:
       - `msg`: the message to print.
    """
    sys.stderr.write(msg)
    sys.stderr.write('\n')


def usage():
    """
    Prints out usage information to stderr.
    """
    print_err('Usage: %s git-binary since' % sys.argv[0])
    print_err(('Example: %s /usr/bin/git f5067523dfae9c7cdefc82'
               '8721ec593ac7be62db' % sys.argv[0]))


def main(args):
    """
    Main entry point.

    :Parameters:
       - `args`: same as sys.argv[1:]
    """
    # Make sure we have the arguments we need, else show usage
    try:
        git_bin = args[0]
        since = args[1]
    except IndexError:
        usage()
        return 1

    if not os.access(git_bin, os.X_OK):
        print_err('Can not access %s' % git_bin)
        return 1

    # Open a pipe and force the format
    pipe = os.popen((git_bin + ' log --pretty="format:%ad  %ae%n'
                     '  * %s" ' + since + '..'))
    print pipe.read()
    pipe.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
