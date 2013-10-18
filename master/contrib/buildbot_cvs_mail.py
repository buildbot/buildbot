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
# Options handling done right by djmitche


"""
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
import sys
import time
import getopt
import socket
import smtplib
import textwrap
import optparse

from cStringIO import StringIO
from email.Utils import formataddr

try:
    import pwd
except:
    # pwd is not available on Windows..
    pwd = None

COMMASPACE = ', '

PROGRAM = sys.argv[0]

class SmtplibMock:
    """I stand in for smtplib for testing purposes.
    """
    class SMTP:
        """I stand in for smtplib.SMTP connection for testing purposes.
        I copy the message to stdout.
        """
        def close(self):
            pass
        def connect(self, mailhost, mailport):
            pass
        def sendmail(self, address, email, msg):
            sys.stdout.write( msg )
        

rfc822_specials_re = re.compile(r'[\(\)\<\>\@\,\;\:\\\"\.\[\]]')

def quotename(name):
    if name and rfc822_specials_re.search(name):
        return '"%s"' % name.replace('"', '\\"')
    else:
        return name

def send_mail(options):
        # Create the smtp connection to the localhost
        conn = options.smtplib.SMTP()
        conn.connect(options.mailhost, options.mailport)
        if pwd:
            pwinfo = pwd.getpwuid(os.getuid())
            user = pwinfo[0]
            name = pwinfo[4]
        else:
            user = 'cvs'
            name = 'CVS'

        domain = options.fromhost
        if not domain:
            # getfqdn is not good for use in unit tests
            if options.amTesting:
                domain = 'testing.com'
            else:
                domain = socket.getfqdn()
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

description="""
This script is used to provide email notifications of changes to the CVS
repository to a buildbot master.  It is invoked via a CVS loginfo file (see
$CVSROOT/CVSROOT/loginfo).  See the Buildbot manual for more information.
"""
usage="%prog [options] %{sVv}"
parser = optparse.OptionParser(description=description,
                    usage=usage,
                    add_help_option=True,
                    version=__version__)

parser.add_option("-C", "--category", dest='category', metavar="CAT",
            help=textwrap.dedent("""\
            Category for change. This becomes the Change.category attribute, which
            can be used within the buildmaster to filter changes.
            """))
parser.add_option("-c", "--cvsroot", dest='cvsroot', metavar="PATH",
            help=textwrap.dedent("""\
            CVSROOT for use by buildbot slaves to checkout code.
            This becomes the Change.repository attribute.
            Exmaple: :ext:myhost:/cvsroot
            """))
parser.add_option("-e", "--email", dest='email', metavar="EMAIL",
            help=textwrap.dedent("""\
            Email address of the buildbot.
            """))
parser.add_option("-f", "--fromhost", dest='fromhost', metavar="HOST",
            help=textwrap.dedent("""\
            The hostname that email messages appear to be coming from.  The From:
            header of the outgoing message will look like user@hostname.  By
            default, hostname is the machine's fully qualified domain name.
            """))
parser.add_option("-m", "--mailhost", dest='mailhost', metavar="HOST",
            default="localhost",
            help=textwrap.dedent("""\
            The hostname of an available SMTP server.  The default is
            'localhost'.
            """))
parser.add_option("--mailport", dest='mailport', metavar="PORT",
            default=25, type="int",
            help=textwrap.dedent("""\
            The port number of SMTP server.  The default is '25'.
            """))
parser.add_option("-q", "--quiet", dest='verbose', action="store_false",
            default=True, 
            help=textwrap.dedent("""\
            Don't print as much status to stdout.
            """))
parser.add_option("-p", "--path", dest='path', metavar="PATH",
            help=textwrap.dedent("""\
            The path for the files in this update. This comes from the %p parameter
            in loginfo for CVS version 1.12.x. Do not use this for CVS version 1.11.x
            """))
parser.add_option("-P", "--project", dest='project', metavar="PROJ",
            help=textwrap.dedent("""\
            The project for the source. Often set to the CVS module being modified. This becomes
            the Change.project attribute.
            """))
parser.add_option("-R", "--reply-to", dest='replyto', metavar="ADDR",
            help=textwrap.dedent("""\
            Add a "Reply-To: ADDR" header to the email message.
            """))
parser.add_option("-t", "--testing", action="store_true", dest="amTesting", default=False)
parser.set_defaults(smtplib=smtplib)

def get_options():
    options, args = parser.parse_args()

    # rest of command line are the files.
    options.files = args
    if options.path is None:
        options.cvsmode = '1.11'
    else:
        options.cvsmode = '1.12'

    if options.cvsroot is None:
        parser.error('--cvsroot is required')
    if options.email is None:
        parser.error('--email is required')

    # set up for unit tests
    if options.amTesting:
        options.verbose = 0
        options.smtplib = SmtplibMock

    return options
        
# scan args for options
def main():
    options = get_options()
    
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
