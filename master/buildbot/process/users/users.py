# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import os

from twisted.python import log
from twisted.internet import defer
from buildbot.status.web import auth, authz

@defer.deferredGenerator
def createUserObject(master, authors, src=None):
    """
    Take a Change author and source and translate them into a User Object,
    storing the user in master.db, or returning None if the src is not
    specified.

    @param master: link to Buildmaster for database operations
    @type master: master.Buildmaster instance

    @param authors: Change author if string or Authz instance
    @type authors: string or status.web.authz instance

    @param src: source from which the User Object will be created, currently
                including 'git' for git Changes and 'authz' for authz from
                master.cfg
    @type src: string
    """

    if not src:
        # handle sendchange changes here
        return

    uid = None
    if src == 'git':
        log.msg("checking for User Object from git Change for: %s" % authors)
        d = parseGitAuthor(authors)
        wfd = defer.waitForDeferred(d)
        yield wfd
        usdict = wfd.getResult()

        d = master.db.users.checkFromGit(usdict)
        wfd = defer.waitForDeferred(d)
        yield wfd
        uid = wfd.getResult()
    elif src == 'authz':
        log.msg("checking for User Objects from Authz in master.cfg")

        d = parseAuthz(authors)
        wfd = defer.waitForDeferred(d)
        yield wfd
        usdicts = wfd.getResult()

        if usdicts:
            for usdict in usdicts:
                d = master.db.users.checkFromAuthz(usdict)
                wfd = defer.waitForDeferred(d)
                yield wfd
                uid = wfd.getResult()
        else:
            log.msg("Unable to check for User Objects from Authz, "
                    "maybe check your master.cfg?")
    yield uid

def parseGitAuthor(author):
    """
    This parses the author string from a change caught from a git
    ChangeSource: buildbot.changes.gitpoller, contrib.git_buildbot and
    contrib.github_buildbot.

    A dictionary with the parsed info is returned via deferred.

    @param author: commiter of change
    @type author: unicode string

    @returns: dictionary via deferred
    """

    full_name = None
    email = None

    if '@' in author:
        email = author.split()[-1]
        if '<' and '>' in email:
            email = email[1:-1]
        full_name = ' '.join(author.split()[:-1])
    else:
        full_name = author
    return defer.succeed(dict(full_name=full_name, email=email))

def parseAuthz(user_authz):
    """
    This takes username/password credentials from an auth.BasicAuth or
    auth.HTPasswdAuth instance and translates them into auth_type/auth_data
    dictionaries that are passed to db.users methods.

    @param user_authz: authz instance as given in the master.cfg
    @type user_authz: auth.BasicAuth or auth.HTPasswdAuth instance

    @returns: list of dicts
    """
    usdicts = []

    try:
        # from auth.BasicAuth
        for username, password in user_authz.auth.userpass:
            usdict = dict(username=username, password=password)
            usdicts.append(usdict)
    except (AttributeError, TypeError): # TypeError for tests with mock
        # from auth.HTPassAuth
        authz_file = user_authz.auth.file
        if not os.path.exists(authz_file):
            log.msg("No such file: " + authz_file)
        else:
            authz_file = open(authz_file, "r")
            authz_lines = authz_file.readlines()
            authz_file.close()
            lines = [l.rstrip().split(':', 1) for l in authz_lines]
            for user in lines:
                usdict = dict(username=user[0], password=user[1])
                usdicts.append(usdict)

    return defer.succeed(usdicts)

def getUserContact(master, contact_type=None, uid=None):
    """
    This is a simple getter function that returns a user attribute
    that matches the contact_type argument, or returns None if no
    uid/match is found.

    @param master: BuildMaster used to query the database
    @type master: BuildMaster instance

    @param contact_type: type of contact attribute to look for in
                         in a given user, such as 'email' or 'nick'
    @type contact_type: string

    @param uid: user that is searched for the contact_type match
    @type uid: integer

    @returns: string of contact information or None via deferred
    """
    d = master.db.users.getUser(uid)
    def getContact(usdict):
        contact = None
        if usdict and contact_type in usdict:
            contact = usdict[contact_type]
        return contact
    d.addCallback(getContact)
    return d
