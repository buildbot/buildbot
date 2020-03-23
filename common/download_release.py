#!/usr/bin/env python3

import os

import requests
import yaml


def download(session, url, fn):
    if os.path.exists(fn):
        print('Removing old file {}'.format(fn))
        os.unlink(fn)
    print('Downloading {} from {}'.format(fn, url))
    with open(fn, 'wb') as f:
        r = session.get(url, stream=True)
        r.raise_for_status()
        for c in r.iter_content(1024):
            f.write(c)


def main():
    with open(os.path.expanduser("~/.config/hub")) as f:
        conf = yaml.safe_load(f)
        token = conf['github.com'][0]['oauth_token']

    s = requests.Session()
    s.headers.update({'Authorization': 'token ' + token})
    r = s.get("https://api.github.com/repos/buildbot/buildbot/releases/latest")
    r.raise_for_status()
    r = r.json()
    tag = r['name']
    upload_url = r['upload_url'].split('{')[0]
    assets = s.get(("https://api.github.com/repos/buildbot/buildbot/releases/{id}/assets"
                    ).format(id=r['id']))
    assets.raise_for_status()
    assets = assets.json()
    os.makedirs('dist', exist_ok=True)
    for url in (a['browser_download_url'] for a in assets):
        if 'gitarchive' in url:
            raise Exception('The git archive has already been uploaded. Are you trying to fix '
                            'broken upload? If this is the case, delete the asset in the GitHub '
                            'UI and retry this command')
        if url.endswith(".whl") or url.endswith(".tar.gz"):
            fn = os.path.join('dist', url.split('/')[-1])
            download(s, url, fn)
    # download tag archive
    url = "https://github.com/buildbot/buildbot/archive/{tag}.tar.gz".format(tag=tag)
    fn = os.path.join('dist', "buildbot-{tag}.gitarchive.tar.gz".format(tag=tag))
    download(s, url, fn)
    sigfn = fn + ".asc"
    if os.path.exists(sigfn):
        os.unlink(sigfn)
    # sign the tag archive for debian
    os.system("gpg --armor --detach-sign --output {} {}".format(sigfn, fn))
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
