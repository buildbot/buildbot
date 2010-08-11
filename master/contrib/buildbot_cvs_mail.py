#!/usr/bin/env python
#
#                        Buildbot CVS Mail
#
# This script was derrived from syncmail, 
# Copyright (c) 2002-2006 Barry Warsaw, Fred Drake, and contributors
#
# http://cvs-syncmail.cvs.sourceforge.net
#
# The script was re-written with the sole pupose of providing updates to
# Buildbot master by Andy Howell
#

"""Buildbot notification for CVS checkins.

This script is used to provide email notifications of changes to the CVS
repository to a buildbot master.

It is invoked via  CVS loginfo file (see $CVSROOT/CVSROOT/loginfo).  To
set this up, create a loginfo entry that looks something like this:

mymodule /path/to/this/script -P mymodule --cvsroot :ext:somehost:/cvsroot -email buildbot@your.domain %%{sVv}

In this example, whenever a checkin that matches `mymodule' is made, this
script is invoked, genating an email to buildbot@your.domain.

For cvs version 1.12.x, the '--path %%p' option is required.

In the buildbot master.cfg, set the source to
c['change_source'] = BultbotCVSMaildirSource("/home/buildbot/Mail" )

Usage:

    %(PROGRAM)s [options] %%{sVv}

Where options are:

    --category=category
    -C
        Catagory for change. This becomes the Change.category attribute.
        This may not make sense to specify it here, as category is meant
        to distinguish the diffrent types of bots inside a same project,
        such as "test", "docs", "full"
        
    --cvsroot=<path>
    -c
        CVSROOT for use by buildbot slaves to checkout code.
        This becomes the Change.repository attribute.
        Exmaple: :ext:myhost:/cvsroot
    
    --email=email
    -e email
        Email address of the buildbot.

    --fromhost=hostname
    -f hostname
        The hostname that email messages appear to be coming from.  The From:
        header of the outgoing message will look like user@hostname.  By
        default, hostname is the machine's fully qualified domain name.

    --help / -h
        Print this text.

    -m hostname
    --mailhost=hostname
        The hostname of an available SMTP server.  The default is
        'localhost'.

    --mailport=port
        The port number of SMTP server.  The default is '25'.

    --quiet / -q
        Don't print as much status to stdout.

    --path=path
    -p path
        The path for the files in this update. This comes from the %%p parameter
        in loginfo for CVS version 1.12.x. Do not use this for CVS version 1.11.x

    --project=project
    -P project
        The project for the source. Use the CVS module being modified. This becomes
        the Change.project attribute.
        
    -R ADDR
    --reply-to=ADDR
      Add a "Reply-To: ADDR" header to the email message.

    -t
    --testing
      Construct message and send to stdout for testing

The rest of the command line arguments are:

    %%{sVv}
        CVS %%{sVv} loginfo expansion.  When invoked by CVS, this will be a single
        string containing the files that are changing.

"""
__version__ = '$Revision: 1.3 $'

import os
import re
import pwd
import sys
import time
import getopt
import socket
import smtplib

from cStringIO import StringIO
from email.Utils import formataddr

COMMASPACE = ', '

PROGRAM = sys.argv[0]

class SmtpMock():
    """I stand in for smtplib.SMTP connection for testing purposes.
    I copy the message to stdout.
    """
    def close(self):
        pass
    def connect(self, mailhost, mailport):
        pass
    def sendmail(self, address, email, msg):
        sys.stdout.write( msg )
        
class SmtplibMock():
    """I stand in for smtplib for testing purposes.
    """
    def SMTP(self):
        return SmtpMock()

class Options():
    """I parse and hold the the command-line options
    """
    def __init__(self):
        self.amTesting = None
        self.category  = None
        self.cvsmode   = None
        self.cvsroot   = None
        self.email     = None
        self.files     = None
        self.fromhost  = None
        self.mailhost  = 'localhost'
        self.mailport  = 25
        self.path      = None
        self.project   = None
        self.replyto   = None
        self.smtp      = smtplib
        self.verbose   = 1

    def dump(self):
        print 'amTesting %s' % self.amTesting
        print 'category  %s' % self.category
        print 'cvsroot   %s' % self.cvsroot
        print 'cvsmode   %s' % self.cvsmode
        print 'email     %s' % self.email
        print 'files     %s' % self.files
        print 'fromhost  %s' % self.fromhost
        print 'mailhost  %s' % self.mailhost
        print 'mailport  %s' % self.mailport
        print 'path      %s' % self.path
        print 'project   %s' % self.project
        print 'replyto   %s' % self.replyto
        print 'verbose   %s' % self.verbose
        
    def usage(self, code, msg=''):
        print __doc__ % globals()
        if msg:
            print msg
            sys.exit(code)

    def parse( self, argv ):
        errcnt = 0
        try:
            opts, args = getopt.getopt(
                argv, 'hc:e:f:m:M:p:P:R:qt',
                ['category=', 'cvsroot=', 'email=', 'fromhost=',
                 'mailhost=', 'mailport=', 'path=', 
                 'reply-to=', 'help', 'quiet', 'testing' ])
        except getopt.error, msg:
            self.usage(1, msg)

        #if not args:
        #    self.usage(1, 'No options specified')

        # parse the options
        for opt, arg in opts:
            if opt in ('-h', '--help'):
                self.usage(0)
                os._exit(0)
            elif opt in ('-C', '--category'):
                self.category = arg
            elif opt in ('-c', '--cvsroot'):
                self.cvsroot = arg
            elif opt in ('-e', '--email'):
                self.email = arg
            elif opt in ('-f', '--fromhost'):
                self.fromhost = arg
            elif opt in ('-m', '--mailhost'):
                self.mailHost = arg
            elif opt in ('--mailport'):
                self.mailPort = arg
            elif opt in ('-p', '--path'):
                self.path = arg
            elif opt in ('-P', '--project'):
                self.project = arg
            elif opt in ('-R', '--reply-to'):
                self.replyto = arg
            elif opt in ('-t', '--testing'):
                self.amTesting = 1 
                self.verbose   = 0
                self.smtp      = SmtplibMock()
            elif opt in ('-q', '--quiet'):
                self.verbose = 0
        # rest of command line are the files.
        self.files = args
        if self.path is None:
            self.cvsmode = '1.11'
        else:
            self.cvsmode = '1.12'
        if self.cvsroot is None:
            print '--cvsroot is required'
            errcnt += 1
        if self.email is None:
            print '--email is required'
            errcnt += 1
            
        return errcnt

rfc822_specials_re = re.compile(r'[\(\)\<\>\@\,\;\:\\\"\.\[\]]')

def quotename(name):
    if name and rfc822_specials_re.search(name):
        return '"%s"' % name.replace('"', '\\"')
    else:
        return name

def send_mail(options):
        # Create the smtp connection to the localhost
        conn = options.smtp.SMTP()
        conn.connect(options.mailhost, options.mailport)
        pwinfo = pwd.getpwuid(os.getuid())
        user = pwinfo[0]
        name = pwinfo[4]
        domain = options.fromhost or socket.getfqdn()
        address = '%s@%s' % (user, domain)
        s = StringIO()
        datestamp = time.strftime('%a, %d %b %Y %H:%M:%S +0000',
                                  time.gmtime(time.time()))
        fileList = ' '.join(map(str, options.files))

        vars = {'author'  : formataddr((name, address)),
                'email'   : options.email,
                'subject' : 'cvs update for project %s' % options.project,
                'version' : __version__,
                'date'    : datestamp,
                }
        print >> s, '''\
From: %(author)s
To: %(email)s''' % vars
        if options.replyto:
            print >> s, 'Reply-To: %s' % options.replyto
        print >>s, '''\
Subject: %(subject)s
Date: %(date)s
X-Mailer: Python buildbot-cvs-mail %(version)s
''' % vars
	print >> s, 'Cvsmode: %s' % options.cvsmode
	print >> s, 'Category: %s' % options.category
	print >> s, 'CVSROOT: %s' % options.cvsroot
	print >> s, 'Files: %s' % fileList
	if options.path:
             print >> s, 'Path: %s' % options.path
	print >> s, 'Project: %s' % options.project
        s.write(sys.stdin.read())
        print >> s
        resp = conn.sendmail(address, options.email, s.getvalue())
        conn.close()
    
def fork_and_send_mail(options):
    # cannot wait for child process or that will cause parent to retain cvs
    # lock for too long.  Urg!
    if not os.fork():
        # in the child
        # give up the lock you cvs thang!
        time.sleep(2)
        send_mail(options)
        os._exit(0)

# scan args for options
def main():
    options = Options()

    # print 'parsing options...'
    if options.parse(sys.argv[1:]) != 0:
        print 'run with --help'
        return 1
    
    # print '... done parsing options'
    # options.dump()
    
    if options.verbose:
        print 'Mailing %s...' % options.email
        print 'Generating notification message...'
    if options.amTesting:
        send_mail(options)
    else:
        fork_and_send_mail(options)
        
    if options.verbose:
        print 'Generating notification message... done.'
    return 0

if __name__ == '__main__':
    ret = main()
    sys.exit(ret)
