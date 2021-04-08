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

import base64
import binascii
import os
import types

from twisted.application import strports
from twisted.conch import manhole
from twisted.conch import telnet
from twisted.conch.insults import insults
from twisted.cred import checkers
from twisted.cred import portal
from twisted.internet import protocol
from twisted.python import log
from zope.interface import implementer  # requires Twisted-2.0 or later

from buildbot import config
from buildbot.util import ComparableMixin
from buildbot.util import service
from buildbot.util import unicode2bytes

try:
    from twisted.conch import checkers as conchc, manhole_ssh
    from twisted.conch.openssh_compat.factory import OpenSSHFactory
    _hush_pyflakes = [manhole_ssh, conchc, OpenSSHFactory]
    del _hush_pyflakes
except ImportError:
    manhole_ssh = None
    conchc = None
    OpenSSHFactory = None


# makeTelnetProtocol and _TelnetRealm are for the TelnetManhole


class makeTelnetProtocol:
    # this curries the 'portal' argument into a later call to
    # TelnetTransport()

    def __init__(self, portal):
        self.portal = portal

    def __call__(self):
        auth = telnet.AuthenticatingTelnetProtocol
        return telnet.TelnetTransport(auth, self.portal)


@implementer(portal.IRealm)
class _TelnetRealm:

    def __init__(self, namespace_maker):
        self.namespace_maker = namespace_maker

    def requestAvatar(self, avatarId, *interfaces):
        if telnet.ITelnetProtocol in interfaces:
            namespace = self.namespace_maker()
            p = telnet.TelnetBootstrapProtocol(insults.ServerProtocol,
                                               manhole.ColoredManhole,
                                               namespace)
            return (telnet.ITelnetProtocol, p, lambda: None)
        raise NotImplementedError()


class chainedProtocolFactory:
    # this curries the 'namespace' argument into a later call to
    # chainedProtocolFactory()

    def __init__(self, namespace):
        self.namespace = namespace

    def __call__(self):
        return insults.ServerProtocol(manhole.ColoredManhole, self.namespace)


if conchc:
    class AuthorizedKeysChecker(conchc.SSHPublicKeyDatabase):

        """Accept connections using SSH keys from a given file.

        SSHPublicKeyDatabase takes the username that the prospective client has
        requested and attempts to get a ~/.ssh/authorized_keys file for that
        username. This requires root access, so it isn't as useful as you'd
        like.

        Instead, this subclass looks for keys in a single file, given as an
        argument. This file is typically kept in the buildmaster's basedir. The
        file should have 'ssh-dss ....' lines in it, just like authorized_keys.
        """

        def __init__(self, authorized_keys_file):
            self.authorized_keys_file = os.path.expanduser(
                authorized_keys_file)

        def checkKey(self, credentials):
            with open(self.authorized_keys_file, "rb") as f:
                for l in f.readlines():
                    l2 = l.split()
                    if len(l2) < 2:
                        continue
                    try:
                        if base64.decodebytes(l2[1]) == credentials.blob:
                            return 1
                    except binascii.Error:
                        continue
            return 0


class _BaseManhole(service.AsyncMultiService):

    """This provides remote access to a python interpreter (a read/exec/print
    loop) embedded in the buildmaster via an internal SSH server. This allows
    detailed inspection of the buildmaster state. It is of most use to
    buildbot developers. Connect to this by running an ssh client.
    """

    def __init__(self, port, checker, ssh_hostkey_dir=None):
        """
        @type port: string or int
        @param port: what port should the Manhole listen on? This is a
        strports specification string, like 'tcp:12345' or
        'tcp:12345:interface=127.0.0.1'. Bare integers are treated as a
        simple tcp port.

        @type checker: an object providing the
        L{twisted.cred.checkers.ICredentialsChecker} interface
        @param checker: if provided, this checker is used to authenticate the
        client instead of using the username/password scheme. You must either
        provide a username/password or a Checker. Some useful values are::
            import twisted.cred.checkers as credc
            import twisted.conch.checkers as conchc
            c = credc.AllowAnonymousAccess # completely open
            c = credc.FilePasswordDB(passwd_filename) # file of name:passwd
            c = conchc.UNIXPasswordDatabase # getpwnam() (probably /etc/passwd)

        @type ssh_hostkey_dir: str
        @param ssh_hostkey_dir: directory which contains ssh host keys for
                                this server
        """

        # unfortunately, these don't work unless we're running as root
        # c = credc.PluggableAuthenticationModulesChecker: PAM
        # c = conchc.SSHPublicKeyDatabase() # ~/.ssh/authorized_keys
        # and I can't get UNIXPasswordDatabase to work

        super().__init__()
        if isinstance(port, int):
            port = "tcp:%d" % port
        self.port = port  # for comparison later
        self.checker = checker  # to maybe compare later

        def makeNamespace():
            master = self.master
            namespace = {
                'master': master,
                'show': show,
            }
            return namespace

        def makeProtocol():
            namespace = makeNamespace()
            p = insults.ServerProtocol(manhole.ColoredManhole, namespace)
            return p

        self.ssh_hostkey_dir = ssh_hostkey_dir
        if self.ssh_hostkey_dir:
            self.using_ssh = True
            if not self.ssh_hostkey_dir:
                raise ValueError("Most specify a value for ssh_hostkey_dir")
            r = manhole_ssh.TerminalRealm()
            r.chainedProtocolFactory = makeProtocol
            p = portal.Portal(r, [self.checker])
            f = manhole_ssh.ConchFactory(p)
            openSSHFactory = OpenSSHFactory()
            openSSHFactory.dataRoot = self.ssh_hostkey_dir
            openSSHFactory.dataModuliRoot = self.ssh_hostkey_dir
            f.publicKeys = openSSHFactory.getPublicKeys()
            f.privateKeys = openSSHFactory.getPrivateKeys()
        else:
            self.using_ssh = False
            r = _TelnetRealm(makeNamespace)
            p = portal.Portal(r, [self.checker])
            f = protocol.ServerFactory()
            f.protocol = makeTelnetProtocol(p)
        s = strports.service(self.port, f)
        s.setServiceParent(self)

    def startService(self):
        if self.using_ssh:
            via = "via SSH"
        else:
            via = "via telnet"
        log.msg("Manhole listening {} on port {}".format(via, self.port))
        return super().startService()


class TelnetManhole(_BaseManhole, ComparableMixin):

    compare_attrs = ("port", "username", "password")

    def __init__(self, port, username, password):
        self.username = username
        self.password = password

        c = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        c.addUser(unicode2bytes(username), unicode2bytes(password))

        super().__init__(port, c)


class PasswordManhole(_BaseManhole, ComparableMixin):

    compare_attrs = ("port", "username", "password", "ssh_hostkey_dir")

    def __init__(self, port, username, password, ssh_hostkey_dir):
        if not manhole_ssh:
            config.error("cryptography required for ssh mahole.")
        self.username = username
        self.password = password
        self.ssh_hostkey_dir = ssh_hostkey_dir

        c = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        c.addUser(unicode2bytes(username), unicode2bytes(password))

        super().__init__(port, c, ssh_hostkey_dir)


class AuthorizedKeysManhole(_BaseManhole, ComparableMixin):

    compare_attrs = ("port", "keyfile", "ssh_hostkey_dir")

    def __init__(self, port, keyfile, ssh_hostkey_dir):
        if not manhole_ssh:
            config.error("cryptography required for ssh mahole.")

        # TODO: expanduser this, and make it relative to the buildmaster's
        # basedir
        self.keyfile = keyfile
        c = AuthorizedKeysChecker(keyfile)
        super().__init__(port, c, ssh_hostkey_dir)


class ArbitraryCheckerManhole(_BaseManhole, ComparableMixin):

    """This Manhole accepts ssh connections, but uses an arbitrary
    user-supplied 'checker' object to perform authentication."""

    compare_attrs = ("port", "checker")

    def __init__(self, port, checker):
        """
        @type port: string or int
        @param port: what port should the Manhole listen on? This is a
        strports specification string, like 'tcp:12345' or
        'tcp:12345:interface=127.0.0.1'. Bare integers are treated as a
        simple tcp port.

        @param checker: an instance of a twisted.cred 'checker' which will
                        perform authentication
        """

        if not manhole_ssh:
            config.error("cryptography required for ssh mahole.")

        super().__init__(port, checker)

# utility functions for the manhole


def show(x):
    """Display the data attributes of an object in a readable format"""
    print("data attributes of %r" % (x,))
    names = dir(x)
    maxlen = max([0] + [len(n) for n in names])
    for k in names:
        v = getattr(x, k)
        if isinstance(v, types.MethodType):
            continue
        if k[:2] == '__' and k[-2:] == '__':
            continue
        if isinstance(v, str):
            if len(v) > 80 - maxlen - 5:
                v = repr(v[:80 - maxlen - 5]) + "..."
        elif isinstance(v, (int, type(None))):
            v = str(v)
        elif isinstance(v, (list, tuple, dict)):
            v = "{} ({} elements)".format(v, len(v))
        else:
            v = str(type(v))
        print("{} : {}".format(k.ljust(maxlen), v))
    return x
