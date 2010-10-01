# strategy:
#
# if there is a VERSION file, use its contents. otherwise, call git to
# get a version string. if that also fails, use 'latest'.
#
import os

version = "latest"

try:
    fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'VERSION')
    version = open(fn).read().strip()

except IOError:
    from subprocess import Popen, PIPE, STDOUT
    import re

    VERSION_MATCH = re.compile(r'\d+\.\d+\.\d+(\w|-)*')

    try:
        p = Popen(['git', 'describe', '--tags', '--always'], stdout=PIPE, stderr=STDOUT)
        out = p.communicate()[0]

        if (not p.returncode) and out:
            v = VERSION_MATCH.search(out)
            if v:
                version = v.group()
    except OSError:
        pass
