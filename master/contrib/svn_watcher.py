#!/usr/bin/python

# This is a program which will poll a (remote) SVN repository, looking for
# new revisions. It then uses the 'buildbot sendchange' command to deliver
# information about the Change to a (remote) buildmaster. It can be run from
# a cron job on a periodic basis, or can be told (with the 'watch' option) to
# automatically repeat its check every 10 minutes.

# This script does not store any state information, so to avoid spurious
# changes you must use the 'watch' option and let it run forever.

# You will need to provide it with the location of the buildmaster's
# PBChangeSource port (in the form hostname:portnum), and the svnurl of the
# repository to watch.


import subprocess
import sys
import time
import xml.dom.minidom
from optparse import OptionParser
from xml.parsers.expat import ExpatError

if sys.platform == 'win32':
    import win32pipe


def getoutput(cmd):
    timeout = 120
    maxtries = 3
    if sys.platform == 'win32':
        f = win32pipe.popen(cmd)
        stdout = ''.join(f.readlines())
        f.close()
    else:
        currentry = 1
        while True:  # retry loop
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            waited = 0
            while True:  # wait loop
                if p.poll() != None:
                    break  # process ended.
                if waited > timeout:
                    print(
                        "WARNING: Timeout of {} seconds reached while trying to run: {}".format(
                            timeout, ' '.join(cmd)
                        )
                    )
                    break
                waited += 1
                time.sleep(1)

            if p.returncode != None:  # process has endend
                stdout = p.stdout.read()
                if p.returncode == 0:
                    break  # ok: exit retry loop
                else:
                    print(
                        'WARNING: "{}" returned status code: {}'.format(' '.join(cmd), p.returncode)
                    )
                    if stdout is not None:
                        print(stdout)
            else:
                p.kill()

            if currentry > maxtries:
                print(
                    "ERROR: Reached maximum number of tries ({}) to run: {}".format(
                        maxtries, ' '.join(cmd)
                    )
                )
                sys.exit(1)
            currentry += 1
    return stdout


def sendchange_cmd(master, revisionData):
    cmd = [
        "buildbot",
        "sendchange",
        f"--master={master}",
        "--revision={}".format(revisionData['revision']),
        "--who={}".format(revisionData['author']),
        "--comments={}".format(revisionData['comments']),
        "--vc={}".format('svn'),
    ]
    if opts.revlink:
        cmd.append("--revlink={}/{}".format(opts.revlink, revisionData['revision']))
    if opts.category:
        cmd.append(f"--category={opts.category}")
    if opts.branch:
        cmd.append(f"--branch={opts.branch}")
    if opts.auth:
        cmd.append(f"--auth={opts.auth}")
    for path in revisionData['paths']:
        cmd.append(path)

    if opts.verbose:
        print(cmd)

    return cmd


def parseChangeXML(raw_xml):
    """Parse the raw xml and return a dict with key pairs set.

    Commmand we're parsing:

    svn log --non-interactive --xml --verbose --limit=1 <repo url>

    With an output that looks like this:

    <?xml version="1.0"?>
     <log>
      <logentry revision="757">
       <author>mwiggins</author>
       <date>2009-11-11T17:16:48.012357Z</date>
       <paths>
        <path kind="" copyfrom-path="/trunk" copyfrom-rev="756" action="A">/tags/Latest</path>
       </paths>
       <msg>Updates/latest</msg>
      </logentry>
     </log>
    """

    data = dict()

    # parse the xml string and grab the first log entry.
    try:
        doc = xml.dom.minidom.parseString(raw_xml)
    except ExpatError:
        print("\nError: Got an empty response with an empty changeset.\n")
        raise
    log_entry = doc.getElementsByTagName("logentry")[0]

    # grab the appropriate meta data we need
    data['revision'] = log_entry.getAttribute("revision")
    data['author'] = "".join([
        t.data for t in log_entry.getElementsByTagName("author")[0].childNodes
    ])
    data['comments'] = "".join([
        t.data for t in log_entry.getElementsByTagName("msg")[0].childNodes
    ])

    # grab the appropriate file paths that changed.
    pathlist = log_entry.getElementsByTagName("paths")[0]
    paths = []
    if opts.branch:
        branchtoken = "/" + opts.branch.strip("/") + "/"
    for path in pathlist.getElementsByTagName("path"):
        filename = "".join([t.data for t in path.childNodes])
        if opts.branch:
            filename = filename.split(branchtoken, 1)[1]
        paths.append(filename)
    data['paths'] = paths

    return data


# FIXME: instead of just picking the last svn change each $interval minutes,
# we should be querying the svn server for all the changes between our
# last check and now, and notify the buildmaster about all of them.
# This is an example of a svn query we could do to get allo those changes:
# svn log --xml --non-interactive -r ${lastrevchecked}:HEAD https://repo.url/branch


def checkChanges(repo, master, oldRevision=-1):
    cmd = ["svn", "log", "--non-interactive", "--xml", "--verbose", "--limit=1", repo]

    if opts.verbose:
        print("Getting last revision of repository: " + repo)

    xml1 = getoutput(cmd)
    pretty_time = time.strftime("%F %T ")

    if opts.verbose:
        print("XML\n-----------\n" + xml1 + "\n\n")

    revisionData = parseChangeXML(xml1)

    if opts.verbose:
        print("PATHS")
        print(revisionData['paths'])

    if revisionData['revision'] != oldRevision:
        cmd = sendchange_cmd(master, revisionData)
        status = getoutput(cmd)

        print("{} Revision {}: {}".format(pretty_time, revisionData['revision'], status))

    else:
        print(
            "{} nothing has changed since revision {}".format(pretty_time, revisionData['revision'])
        )

    return revisionData['revision']


def build_parser():
    usagestr = "%prog [options] <repo url> <buildbot master:port>"
    parser = OptionParser(usage=usagestr)

    parser.add_option(
        "-c",
        "--category",
        dest="category",
        action="store",
        default="",
        help="""Store a category name to be associated with sendchange msg.""",
    )

    parser.add_option(
        "-i",
        "--interval",
        dest="interval",
        action="store",
        default=0,
        help="Implies watch option and changes the time in minutes to the value specified.",
    )

    parser.add_option(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="Enables more information to be presented on the command line.",
    )

    parser.add_option(
        "-b",
        "--branch",
        dest="branch",
        action="store",
        default=None,
        help="Watch only changes for this branch and send the branch info.",
    )

    parser.add_option(
        "-a",
        "--auth",
        dest="auth",
        action="store",
        default=None,
        help="Authentication token - username:password.",
    )

    parser.add_option(
        "-l",
        "--link",
        dest="revlink",
        action="store",
        default=None,
        help="A base URL for the revision links.",
    )

    parser.add_option(
        "",
        "--watch",
        dest="watch",
        action="store_true",
        default=False,
        help="Automatically check the repo url every 10 minutes.",
    )

    return parser


def validate_args(args):
    """Validate our arguments and exit if we don't have what we want."""
    if not args:
        print("\nError: No arguments were specified.\n")
        parser.print_help()
        sys.exit(1)
    elif len(args) > 2:
        print("\nToo many arguments specified.\n")
        parser.print_help()
        sys.exit(2)


if __name__ == '__main__':
    # build our parser and validate our args
    parser = build_parser()
    (opts, args) = parser.parse_args()
    validate_args(args)
    if opts.interval:
        try:
            int(opts.interval)
        except ValueError:
            print("\nError: Value of the interval option must be a number.")
            parser.print_help()
            sys.exit(3)

    # grab what we need
    repo_url = args[0]
    bbmaster = args[1]

    if opts.branch:
        repo_url = repo_url.rstrip("/") + "/" + opts.branch.lstrip("/")

    # if watch is specified, run until stopped
    if opts.watch or opts.interval:
        oldRevision = -1
        print(f"Watching for changes in repo {repo_url} for master {bbmaster}.")
        while True:
            try:
                oldRevision = checkChanges(repo_url, bbmaster, oldRevision)
            except ExpatError:
                # had an empty changeset.  Trapping the exception and moving
                # on.
                pass
            try:
                if opts.interval:
                    # Check the repository every interval in minutes the user
                    # specified.
                    time.sleep(int(opts.interval) * 60)
                else:
                    # Check the repository every 10 minutes
                    time.sleep(10 * 60)
            except KeyboardInterrupt:
                print("\nReceived interrupt via keyboard.  Shutting Down.")
                sys.exit(0)

    # default action if watch isn't specified
    checkChanges(repo_url, bbmaster)
