#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function

import argparse
import os
import re
import sys
from subprocess import PIPE
from subprocess import STDOUT
from subprocess import check_call
from subprocess import check_output

import requests


def parse_chrome_major_version(output):
    for line in output.splitlines():
        # e.g.:
        # Chromium 69.0.3497.81 Built on Ubuntu , running on Ubuntu 18.04
        # Google Chrome 70.0.3538.77
        m = re.match(r'.*[cC]hrom.*\s(\d+)\.(\d+)\.(\d+)(?:\.\d+|).*', line)
        if m is not None:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


def get_chrome_version(browsers):
    for browser in browsers:
        try:
            # FIXME: Use subprocess.DEVNULL on python3
            output = check_output([browser + ' --version'],
                                  stderr=None, shell=True)
            output = output.decode('utf-8', errors='ignore')

            version = parse_chrome_major_version(output)
            if version is not None:
                return (browser, version)
        except Exception:
            pass
    return (None, None)


def get_chromedriver_compatibility_map():
    chromedriver_root = 'https://chromedriver.storage.googleapis.com'

    r = requests.get('{0}/LATEST_RELEASE'.format(chromedriver_root))
    if r.status_code != 200:
        raise Exception('Could not get newest chromedriver version')

    chromedriver_newest_release = r.text

    r = requests.get('{0}/{1}/notes.txt'.format(chromedriver_root,
                                                chromedriver_newest_release))
    if r.status_code != 200:
        raise Exception('Could not get chromedriver v{0} notes.txt'.format(
            chromedriver_newest_release))

    return parse_chromedriver_compatibility_map(r.text)


def main():
    parser = argparse.ArgumentParser(
        prog='smokedist-download-compatible-chromedriver')

    parser.add_argument('manager', type=str,
                        help="Path to the webdriver-manager")
    parser.add_argument('browsers', type=str, nargs='+',
                        help="The browsers to get version info from. The first "
                             "existing browser from the list will be used")
    args = parser.parse_args()

    try:
        browser, version = get_chrome_version(args.browsers)
        if browser is None:
            raise Exception('Could no get browser version')

        print('Using {0} release {1}'.format(browser, version))

        chrome_major, chrome_minor, chrome_patch = version

        if chrome_major >= 73:
            # webdriver manager requires us to provide the 4th version component, however does not
            # use it when picking the version to download
            chromedriver_version = '{}.{}.{}.0'.format(chrome_major, chrome_minor, chrome_patch)
        else:
            chrome_major_to_chromedriver = {
                73: '2.46',
                72: '2.46',
                71: '2.46',
                70: '2.45',
                69: '2.44',
            }
            if chrome_major not in chrome_major_to_chromedriver:
                raise Exception('Unknown Chrome version {}.{}.{}'.format(
                    chrome_major, chrome_minor, chrome_patch))
            chromedriver_version = chrome_major_to_chromedriver[chrome_major]

        print('Using chromedriver release {0}'.format(chromedriver_version))

        cmd = [args.manager, 'update', '--versions.chrome',
               chromedriver_version, '--versions.standalone', '3.141.59']
        print('Calling: ' + ' '.join(cmd))

        check_call(cmd)

        return

    except Exception as e:
        print(str(e))
        print('Failed to get compatible chromedriver version, using latest')

    check_call([args.manager + ' update'], shell=True)


if __name__ == '__main__':
    main()
