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

