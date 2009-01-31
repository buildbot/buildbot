# Dan Radez <dradez+buildbot@redhat.com>
# Steve 'Ashcrow' Milner <smilner+buildbot@redhat.com>
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
"""
library to populate parameters from and rpmspec file into a memory structure
"""


from buildbot.steps.shell import ShellCommand


class RpmSpec(ShellCommand):
    """
    read parameters out of an rpm spec file
    """

    import re
    import types

    #initialize spec info vars and get them from the spec file
    n_regex = re.compile('^Name:[ ]*([^\s]*)')
    v_regex = re.compile('^Version:[ ]*([0-9\.]*)')

    def __init__(self, specfile=None, **kwargs):
        """
        Creates the RpmSpec object.

        @type specfile: str
        @param specfile: the name of the specfile to get the package
            name and version from
        @type kwargs: dict
        @param kwargs: All further keyword arguments.
        """
        self.specfile = specfile
        self._pkg_name = None
        self._pkg_version = None
        self._loaded = False

    def load(self):
        """
        call this function after the file exists to populate properties
        """
        # If we are given a string, open it up else assume it's something we
        # can call read on.
        if type(self.specfile) == self.types.StringType:
            f = open(self.specfile, 'r')
        else:
            f = self.specfile

        for line in f:
            if self.v_regex.match(line):
                self._pkg_version = self.v_regex.match(line).group(1)
            if self.n_regex.match(line):
                self._pkg_name = self.n_regex.match(line).group(1)
        f.close()
        self._loaded = True

    # Read-only properties
    loaded = property(lambda self: self._loaded)
    pkg_name = property(lambda self: self._pkg_name)
    pkg_version = property(lambda self: self._pkg_version)
