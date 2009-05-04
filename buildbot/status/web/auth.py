
import os
from zope.interface import Interface, implements
from buildbot.status.web.base import HtmlResource

class IAuth(Interface):
    """Represent an authentication method."""

    def authenticate(self, user, passwd):
            """Check whether C{user} / C{passwd} are valid."""

    def errmsg(self):
            """Get the reason authentication failed."""

class AuthBase:
    err = ""

    def errmsg(self):
        return self.err

class BasicAuth(AuthBase):
    implements(IAuth)
    """Implement basic authentication against a list of user/passwd."""

    userpass = []
    """List of user/pass tuples."""

    def __init__(self, userpass):
        """C{userpass} is a list of (user, passwd)."""
        for item in userpass:
            assert isinstance(item, tuple)
            u, p = item
            assert isinstance(u, str)
            assert isinstance(p, str)
        self.userpass = userpass

    def authenticate(self, user, passwd):
        """Check that C{user}/C{passwd} is a valid user/pass tuple."""
        if not self.userpass:
            self.err = "Bad self.userpass data"
            return False
        for u, p in self.userpass:
            if user == u and passwd == p:
                self.err = ""
                return True
        self.err = "Invalid username or password"
        return False

class HTPasswdAuth(AuthBase):
    implements(IAuth)
    """Implement authentication against an .htpasswd file."""

    file = ""
    """Path to the .htpasswd file to use."""

    def __init__(self, file):
        """C{file} is a path to an .htpasswd file."""
        assert os.path.exists(file)
        self.file = file

    def authenticate(self, user, passwd):
        """Authenticate C{user} and C{passwd} against an .htpasswd file"""
        if not os.path.exists(self.file):
            self.err = "No such file: " + self.file
            return False
        # Fetch each line from the .htpasswd file and split it into a
        # [user, passwd] array.
        lines = [l.rstrip().split(':', 1)
                 for l in file(self.file).readlines()]
        # Keep only the line for this login
        lines = [l for l in lines if l[0] == user]
        if not lines:
            self.err = "Invalid user/passwd"
            return False
        # This is the DES-hash of the password. The first two characters are
        # the salt used to introduce disorder in the DES algorithm.
        hash = lines[0][1]
        from crypt import crypt
        res = hash == crypt(passwd, hash[0:2])
        if res:
            self.err = ""
        else:
            self.err = "Invalid user/passwd"
        return res

class AuthFailResource(HtmlResource):
    title = "Authentication Failed"

    def body(self, request):
        data = ''
        data += '<h1>Authentication Failed</h1>\n'
        data += '<p>The username or password you entered were not correct.  Please go back and try again.</p>\n'

        return data

