import types
import time

def remove_userpassword(url):
    if '@' not in url:
        return url
    if '://' not in url:
        return url

    # urlparse would've been nice, but doesn't support ssh... sigh    
    protocol_url = url.split('://')
    protocol = protocol_url[0]
    repo_url = protocol_url[1].split('@')[-1]

    return protocol + '://' + repo_url


def now(_reactor=None):
    if _reactor and hasattr(_reactor, "seconds"):
        return _reactor.seconds()
    else:
        return time.time()

class Obfuscated:
    """An obfuscated string in a command"""
    def __init__(self, real, fake):
        self.real = real
        self.fake = fake

    def __str__(self):
        return self.fake

    def __repr__(self):
        return `self.fake`

    @staticmethod
    def to_text(s):
        if isinstance(s, (str, unicode)):
            return s
        else:
            return str(s)

    @staticmethod
    def get_real(command):
        rv = command
        if type(command) == types.ListType:
            rv = []
            for elt in command:
                if isinstance(elt, Obfuscated):
                    rv.append(elt.real)
                else:
                    rv.append(Obfuscated.to_text(elt))
        return rv

    @staticmethod
    def get_fake(command):
        rv = command
        if type(command) == types.ListType:
            rv = []
            for elt in command:
                if isinstance(elt, Obfuscated):
                    rv.append(elt.fake)
                else:
                    rv.append(Obfuscated.to_text(elt))
        return rv

