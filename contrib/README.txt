Utility scripts:

debugclient.py (and debug.*): debugging gui for buildbot

fakechange.py: connect to a running bb and submit a fake change to trigger
               builders

run_maxq.py: a builder-helper for running maxq under buildbot

svn_buildbot.py: a script intended to be run from a subversion hook-script
                 which submits changes to svn (requires python 2.3)
