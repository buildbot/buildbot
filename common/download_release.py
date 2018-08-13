from __future__ import absolute_import
from __future__ import print_function

import os

import requests
import yaml


def download(url, fn):
    print(url, fn)
    if os.path.exists(fn):
        return
    with open(fn, 'w') as f:
        r = s.get(url, stream=True)
        for c in r.iter_content(1024):
            f.write(c)

def main():
    global s
    with open(os.path.expanduser("~/.config/hub")) as f:
        conf = yaml.load(f)
        token = conf['github.com'][0]['oauth_token']

    s = requests.Session()
    s.headers.update({'Authorization': 'token ' + token})
    r = s.get("https://api.github.com/repos/buildbot/buildbot/releases/latest")
    r.raise_for_status()
    r = r.json()
    tag = r['name']
    upload_url = r['upload_url'].split('{')[0]
    assets = s.get("https://api.github.com/repos/buildbot/buildbot/releases/{id}/assets".format(id=r['id']))
    assets.raise_for_status()
    assets = assets.json()
    os.system("mkdir -p dist")
    for url in (a['browser_download_url'] for a in assets):
        if url.endswith(".whl") or url.endswith(".tar.gz"):
            fn = os.path.join('dist', url.split('/')[-1])
            download(url, fn)
    # download tag archive
    url = "https://github.com/buildbot/buildbot/archive/{tag}.tar.gz".format(tag=tag)
    fn = os.path.join('dist', "buildbot-{tag}.gitarchive.tar.gz".format(tag=tag))
    download(url, fn)
    sigfn = fn + ".sig"
    if os.path.exists(sigfn):
        os.unlink(sigfn)
    # sign the tag archive for debian
    os.system("gpg --output {} -b {}".format(sigfn, fn))
    sigfnbase = os.path.basename(sigfn)
    r = s.post(upload_url,
               headers={'Content-Type': "application/pgp-signature"},
               params={"name": sigfnbase},
               data=open(sigfn, 'rb'))
    print(r.content)
    fnbase = os.path.basename(fn)
    r = s.post(upload_url,
               headers={'Content-Type': "application/gzip"},
               params={"name": fnbase},
               data=open(fn, 'rb'))
    print(r.content)
    # remove files so that twine upload do not upload them
    os.unlink(sigfn)
    os.unlink(fn)
if __name__ == '__main__':
    main()
