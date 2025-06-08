#!/usr/bin/env python3

# this script takes all the PR created by dependabot and gather them into one

import os
import subprocess

import requests
import yaml


def main():
    with open(os.path.expanduser("~/.config/hub")) as f:
        conf = yaml.safe_load(f)
        token = conf['github.com'][0]['oauth_token']

    subprocess.check_call(["git", "fetch", "https://github.com/buildbot/buildbot", "master"])
    subprocess.check_call(["git", "checkout", "FETCH_HEAD", "-B", "gather_dependabot"])
    s = requests.Session()
    s.headers.update({'Authorization': 'token ' + token})
    r = s.get("https://api.github.com/repos/buildbot/buildbot/pulls")
    r.raise_for_status()
    prs = r.json()

    pr_text = "This PR collects dependabot PRs:\n\n"
    try:
        for pr in prs:
            if 'dependabot' in pr['user']['login']:
                print(pr['number'], pr['title'])
                subprocess.check_call([
                    "git",
                    "fetch",
                    "https://github.com/buildbot/buildbot",
                    f"refs/pull/{pr['number']}/head",
                ])
                subprocess.check_call(["git", "cherry-pick", "master..FETCH_HEAD"])
                pr_text += f"#{pr['number']}: {pr['title']}\n"
    except Exception as e:
        print('GOT ERROR', e)

    print("===========")
    print(pr_text)


if __name__ == '__main__':
    main()
