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

try:
    from hashlib import md5
    assert md5
except ImportError:
    # For Python 2.4
    import md5

srcs = ['git', 'svn', 'hg', 'cvs', 'darcs', 'bzr']
salt_len = 8

@defer.deferredGenerator
def createUserObject(master, author, src=None):
    """
    Take a Change author and source and translate them into a User Object,
    storing the user in master.db, or returning None if the src is not
    specified.

    @param master: link to Buildmaster for database operations
    @type master: master.Buildmaster instance

    @param authors: Change author if string or Authz instance
    @type authors: string or status.web.authz instance

    @param src: source from which the User Object will be created
    @type src: string
    """

    if not src:
        log.msg("No vcs information found, unable to create User Object")
        return

    if src in srcs:
        log.msg("checking for User Object from %s Change for: %s" % (src,
                                                                     author))
        usdict = dict(identifier=author, attr_type=src, attr_data=author)
    else:
        log.msg("Unrecognized source argument: %s" % src)
        return

    d = master.db.users.addUser(identifier=usdict['identifier'],
                                bb_username=None, bb_password=None,
                                attr_type=usdict['attr_type'],
                                attr_data=usdict['attr_data'])
    wfd = defer.waitForDeferred(d)
    yield wfd
    uid = wfd.getResult()

    yield uid

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
    d.addCallback(lambda usdict: usdict and usdict.get(contact_type))
    return d

def encrypt(passwd):
    """
    Encrypts the incoming password after adding some salt to store
    it in the database.

    @param passwd: password portion of user credentials
    @type passwd: string

    @returns: encrypted/salted string
    """
    try:
        m = md5()
    except TypeError:
        m = md5.new()

    salt = os.urandom(salt_len).encode('hex_codec')
    m.update(passwd + salt)
    crypted = salt + m.hexdigest()
    return crypted

def check_passwd(guess, passwd):
    """
    Tests to see if the guess, after salting and hashing, matches the
    passwd from the database.

    @param guess: incoming password trying to be used for authentication
    @param passwd: already encrypted password from the database

    @returns: boolean
    """
    try:
        m = md5()
    except TypeError:
        m = md5.new()

    salt = passwd[:salt_len * 2]  # salt_len * 2 due to encode('hex_codec')
    m.update(guess + salt)
    crypted_guess = salt + m.hexdigest()

    return (crypted_guess == passwd)
