from __future__ import absolute_import
from __future__ import print_function

import os

import requests
import yaml


def main():
    with open(os.path.expanduser("~/.config/hub")) as f:
        conf = yaml.load(f)
        token = conf['github.com'][0]['oauth_token']

    s = requests.Session()
    s.headers.update({'Authorization': 'token ' + token})
    r = s.get("https://api.github.com/repos/buildbot/buildbot/releases/latest")
    r.raise_for_status()
    r = r.json()
    assets = s.get("https://api.github.com/repos/buildbot/buildbot/releases/{id}/assets".format(id=r['id']))
    assets.raise_for_status()
    assets = assets.json()
    os.system("rm -rf dist")
    os.system("mkdir -p dist")
    for url in (a['browser_download_url'] for a in assets):
        if url.endswith(".whl") or url.endswith(".tar.gz"):
            print(url)
            os.system("wget -P dist/ {url}".format(url=url))


if __name__ == '__main__':
    main()
