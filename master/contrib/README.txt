Utility scripts, things contributed by users but not strictly a part of
buildbot:

buildbot_json.py: Utility classes and standalone script to process data from
                  /json status.

fakechange.py: connect to a running bb and submit a fake change to trigger
               builders

generate_changelog.py: generated changelog entry using git. Requires git to
                       be installed.

run_maxq.py: a builder-helper for running maxq under buildbot

svn_buildbot.py: a script intended to be run from a subversion hook-script
                 which submits changes to svn (requires python 2.3)

svnpoller.py: this script is intended to be run from a cronjob, and uses 'svn
              log' to poll a (possibly remote) SVN repository for changes.
              For each change it finds, it runs 'buildbot sendchange' to
              deliver them to a waiting PBChangeSource on a (possibly remote)
              buildmaster. Modify the svnurl to point at your own SVN
              repository, and of course the user running the script must have
              read permissions to that repository. It keeps track of the last
              revision in a file, change 'fname' to set the location of this
              state file. Modify the --master argument to the 'buildbot
              sendchange' command to point at your buildmaster. Contributed
              by John Pye. Note that if there are multiple changes within a
              single polling interval, this will miss all but the last one.

svn_watcher.py: adapted from svnpoller.py by Niklaus Giger to add options and
                run under windows. Runs as a standalone script (it loops
                internally rather than expecting to run from a cronjob),
                polls an SVN repository every 10 minutes. It expects the
                svnurl and buildmaster location as command-line arguments.

viewcvspoll.py: a standalone script which loops every 60 seconds and polls a
                (local?) MySQL database (presumably maintained by ViewCVS?)
                for information about new CVS changes, then delivers them
                over PB to a remote buildmaster's PBChangeSource. Contributed
                by Stephen Kennedy.

css/*.css: alternative HTML stylesheets to make the Waterfall display look
           prettier. Copy them somewhere, then pass the filename to the
           css= argument of the Waterfall() constructor.

zsh/_buildbot: zsh tab-completion file for 'buildbot' command. Put it in one
               of the directories appearing in $fpath to enable tab-completion
               in zsh.

bash/buildbot: bash tab-completion file for 'buildbot' command. Source this
               file to enable completions in your bash session. This is
               typically accomplished by placing the file into the
               appropriate 'bash_completion.d' directory.

SimpleConfig.py: an example of how to configure buildbot using a declarative
                 json file plus one buildshim script per project

api_proxy.py: a simple flask application to help web ui development
              it will proxy the api request to a production buildbot instance
              This helps the ui developer to test dashboards with real data 
              please pip install flask requests on top of the usual buildbot
              virtualenv to make it work
