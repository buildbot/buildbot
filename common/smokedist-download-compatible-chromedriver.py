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
        m = re.match(r'.*[cC]hrom.*\s(\d+)\.\d+\.\d+(?:\.\d+|).*', line)
        if m is not None:
            return int(m.group(1))
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


def parse_chromedriver_compatibility_map(notes):
    ret = {}
    lines = notes.splitlines()
    for i in range(len(lines) - 1):
        m1 = re.match(r'--+ChromeDriver v(\d+\.\d+) .*', lines[i])
        m2 = re.match(r'Supports Chrome v(\d+)-(\d+).*', lines[i+1])
        m3 = re.match(r'Supports Chrome v(\d+).*', lines[i+1])
        if m1 is not None and (m2 is not None or m3 is not None):
            chromedrive_version = m1.group(1)
            if m2 is not None:
                chrome_version_min = int(m2.group(1))
                chrome_version_max = int(m2.group(2)) + 1
            else:
                chrome_version_min = int(m3.group(1))
                chrome_version_max = int(m3.group(1)) + 1
            for version in range(chrome_version_min, chrome_version_max):
                # prefer newer chromedriver, assuming it is first in notes
                if version not in ret:
                    ret[version] = chromedrive_version

    return ret


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

        compat_map = get_chromedriver_compatibility_map()

        if version not in compat_map:
            raise Exception('Unknown {0} version {1}'.format(browser, version))

        chromedriver_version = compat_map[version]
        print('Using chromedriver release {0}'.format(chromedriver_version))

        check_call([args.manager + ' update --versions.chrome ' +
                   chromedriver_version], shell=True)
        return

    except Exception as e:
        print(str(e))
        print('Failed to get compatible chromedriver version, using latest')

    check_call([args.manager + ' update'], shell=True)


if __name__ == '__main__':
    main()
