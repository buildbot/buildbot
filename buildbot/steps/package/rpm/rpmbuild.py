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
RPM Building steps.
"""

from buildbot.steps.shell import ShellCommand
from buildbot.process.buildstep import RemoteShellCommand


class RpmBuild(ShellCommand):
    """
    Build and RPM based on pased spec filename
    """

    import os.path

    name = "rpmbuilder"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["RPMBUILD"]
    descriptionDone = ["RPMBUILD"]

    def __init__(self,
                 specfile=None,
                 topdir='`pwd`',
                 builddir='`pwd`',
                 rpmdir='`pwd`',
                 sourcedir='`pwd`',
                 specdir='`pwd`',
                 srcrpmdir='`pwd`',
                 dist='.el5',
                 autoRelease=False,
                 vcsRevision=False,
                 **kwargs):
        """
        Creates the RpmBuild object.

        @type specfile: str
        @param specfile: the name of the spec file for the rpmbuild
        @type topdir: str
        @param topdir: the top directory for rpm building.
        @type builddir: str
        @param builddir: the directory to use for building
        @type rpmdir: str
        @param rpmdir: the directory to dump the rpms into
        @type sourcedir: str
        @param sourcedir: the directory that houses source code
        @type srcrpmdir: str
        @param srcrpmdir: the directory to dump source rpms into
        @type dist: str
        @param dist: the distribution to build for
        @type autoRelease: boolean
        @param autoRelease: if the auto release mechanics should be used
        @type vcsRevision: boolean
        @param vcsRevision: if the vcs revision mechanics should be used
        @type kwargs: dict
        @param kwargs: All further keyword arguments.
        """
        ShellCommand.__init__(self, **kwargs)
        self.addFactoryArguments(topdir=topdir,
                                 builddir=builddir,
                                 rpmdir=rpmdir,
                                 sourcedir=sourcedir,
                                 specdir=specdir,
                                 srcrpmdir=srcrpmdir,
                                 specfile=specfile,
                                 dist=dist,
                                 autoRelease=autoRelease,
                                 vcsRevision=vcsRevision)
        self.rpmbuild = (
            'rpmbuild --define "_topdir %s" --define "_builddir %s"'
            ' --define "_rpmdir %s" --define "_sourcedir %s"'
            ' --define "_specdir %s" --define "_srcrpmdir %s"'
            ' --define "dist %s"' % (topdir, builddir, rpmdir, sourcedir,
            specdir, srcrpmdir, dist))
        self.specfile = specfile
        self.autoRelease = autoRelease
        self.vcsRevision = vcsRevision

    def start(self):
        """
        Buildbot Calls Me when it's time to start
        """
        if self.autoRelease:
            relfile = '%s.release' % (
                self.os.path.basename(self.specfile).split('.')[0])
            try:
                rfile = open(relfile, 'r')
                rel = int(rfile.readline().strip())
                rfile.close()
            except:
                rel = 0
            self.rpmbuild = self.rpmbuild + ' --define "_release %s"' % rel
            rfile = open(relfile, 'w')
            rfile.write(str(rel+1))
            rfile.close()

        if self.vcsRevision:
            self.rpmbuild = self.rpmbuild + ' --define "_revision %s"' % \
                self.getProperty('got_revision')

        self.rpmbuild = self.rpmbuild + ' -ba %s' % self.specfile

        self.command = ['bash', '-c', self.rpmbuild]

        # create the actual RemoteShellCommand instance now
        kwargs = self.remote_kwargs
        kwargs['command'] = self.command
        cmd = RemoteShellCommand(**kwargs)
        self.setupEnvironment(cmd)
        self.checkForOldSlaveAndLogfiles()
        self.startCommand(cmd)

    def createSummary(self, log):
        """
        Create nice summary logs.

        @param log: The log to create summary off of.
        """
        rpm_prefixes = ['Provides:', 'Requires(rpmlib):', 'Requires:',
                        'Checking for unpackaged', 'Wrote:',
                        'Executing(%', '+ ']
        rpm_err_pfx = ['   ', 'RPM build errors:', 'error: ']

        rpmcmdlog = []
        rpmerrors = []

        for line in log.readlines():
            for pfx in rpm_prefixes:
                if pfx in line:
                    rpmcmdlog.append(line)
            for err in rpm_err_pfx:
                if err in line:
                    rpmerrors.append(line)
        self.addCompleteLog('RPM Command Log', "".join(rpmcmdlog))
        self.addCompleteLog('RPM Errors', "".join(rpmerrors))
