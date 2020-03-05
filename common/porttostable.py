from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
from subprocess import CalledProcessError
from subprocess import check_output

import requests
import yaml

s = requests.Session()
with open(os.path.expanduser('~/.config/hub')) as f:
    config = yaml.load(f)['github.com'][0]
    s.auth = config['user'], config['oauth_token']

os.system("git fetch --all")
r = s.get("https://api.github.com/search/issues?q=label:\"port%20to%20stable\"+repo:buildbot/buildbot") # noqa pylint: disable=line-too-long
to_port = r.json()
summary = ""
for pr in to_port['items']:
    r = s.get("https://api.github.com/repos/buildbot/buildbot/pulls/{number}/commits".format(**pr))
    commits = r.json()
    for c in commits:
        title = c['commit']['message'].split("\n")[0]
        try:
            check_output("git cherry-pick {sha} 2>&1".format(**c), shell=True)
        except CalledProcessError as e:
            os.system("git diff")
            os.system("git reset --hard HEAD 2>&1 >/dev/null")
            if '--allow-empty' in e.output:
                continue
            if 'fatal: bad object' in e.output:
                continue
            print("cannot automatically cherry-pick", pr['number'], c['sha'], title, e.output)
        else:
            summary += "\n#{number}: {title}".format(number=pr['number'], title=title, **c)
print(summary)
