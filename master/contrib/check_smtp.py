#! /usr/bin/python -tt

from __future__ import division
from __future__ import print_function

from getpass import getpass
from smtplib import SMTP

"""
This script helps to check that the SMTP_HOST (see below) would accept STARTTLS
command, and if LOCAL_HOST is acceptable for it, would check the requested user
name and password would allow to send e-mail through it.
"""


SMTP_HOST = 'the host you want to send e-mail through'
LOCAL_HOST = 'hostname that the SMTP_HOST would accept'


def main():
    """
    entry point
    """

    server = SMTP(SMTP_HOST)

    server.starttls()

    print(server.ehlo(LOCAL_HOST))

    user = raw_input('user: ')
    password = getpass('password: ')

    print(server.login(user, password))
    server.close()

if __name__ == '__main__':
    main()

# vim:ts=4:sw=4:et:tw=80
