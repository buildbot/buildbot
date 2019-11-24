#!/usr/bin/env python3

import argparse
import re
from subprocess import DEVNULL
from subprocess import check_call
from subprocess import check_output


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
            print([browser, ' --version'])
            output = check_output([browser, ' --version'],
                                  stderr=DEVNULL)
            output = output.decode('utf-8', errors='ignore')

            version = parse_chrome_major_version(output)
            if version is not None:
                return (browser, version)
        except Exception:
            pass
    return (None, None)


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
