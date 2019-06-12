#!/usr/bin/env python3


import argparse
import json
import os
import shutil
import subprocess


def checkout_buildbot_at_revision(curr_buildbot_root, test_buildbot_root, revision):
    if os.path.isdir(test_buildbot_root):
        print('Removing {}'.format(test_buildbot_root))
        shutil.rmtree(test_buildbot_root)
    os.makedirs(test_buildbot_root)

    subprocess.check_call(['git', 'clone', curr_buildbot_root, test_buildbot_root])
    subprocess.check_call(['git', 'reset', '--hard', revision], cwd=test_buildbot_root)


def install_local_dependencies(curr_buildbot_root, test_buildbot_root):
    packages = [
        # data_module must be first, then guanlecoja-ui, as other packages depend on them
        'www/data_module',
        'www/guanlecoja-ui',

        'www/base',
        'www/codeparameter',
        'www/console_view',
        'www/grid_view',
        'www/waterfall_view',
        'www/wsgi_dashboards',
    ]

    for package in packages:
        package_root = os.path.join(test_buildbot_root, package)
        package_json_path = os.path.join(package_root, 'package.json')

        with open(package_json_path) as in_f:
            contents = json.load(in_f)
        if 'scripts' not in contents:
            raise Exception('Unexpected package.json for {}'.format(package))
        if 'yarn-update-local' not in contents['scripts']:
            raise Exception('Unexpected package.json for {}'.format(package))
        yarn_cmd = contents['scripts']['yarn-update-local']

        # we delete the yarn-update-local script so that the package builder does not reinstall
        # the old local dependencies when building python packages.
        del contents['scripts']['yarn-update-local']
        with open(package_json_path, 'w') as out_f:
            json.dump(contents, out_f, indent=4, sort_keys=True)

        replacements = [
            ('../data_module', os.path.join(curr_buildbot_root, 'www/data_module')),
            ('../guanlecoja-ui', os.path.join(curr_buildbot_root, 'www/guanlecoja-ui')),
            ('../build_common', os.path.join(curr_buildbot_root, 'www/build_common')),
        ]

        for old, new in replacements:
            yarn_cmd = yarn_cmd.replace(old, new)

        if '../' in yarn_cmd:
            raise Exception('Not all local dependencies have been replaced: {}'.format(yarn_cmd))

        # Note that we don't reset yarn.lock during this test even though `yarn add` and
        # `yarn remove` commands will modify it. The new local dependencies may have different or
        # newer sub-dependencies which may in fact need to be updated.
        #
        # Also note that `yarn install` will be run by the test script
        print('Running: {}'.format(yarn_cmd))
        subprocess.check_call(yarn_cmd, shell=True, cwd=package_root)


def run_test(test_buildbot_root):
    subprocess.check_call(['make', 'tarballs'], cwd=test_buildbot_root)
    subprocess.check_call(['common/smokedist.sh', 'whl'], cwd=test_buildbot_root)


def main():
    parser = argparse.ArgumentParser(prog='smokedist-www-backwards-compat')

    parser.add_argument('revision', type=str,
                        help="A commit or tag that is accepted by git to test against")
    parser.add_argument('--tmp-path', type=str, default=None,
                        help="The path to checkout old Buildbot version to")
    parser.add_argument('--dont-clean', action='store_true', default=False,
                        help="If set, the temporary buildbot checkout will not be deleted")
    args = parser.parse_args()

    curr_buildbot_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if args.tmp_path is not None:
        test_buildbot_root = args.tmp_path
    else:
        test_buildbot_root = os.path.join(curr_buildbot_root, 'tmp-buildbot-smokedist')
        print('Using {} as temporary path for buildbot checkout'.format(test_buildbot_root))

    checkout_buildbot_at_revision(curr_buildbot_root, test_buildbot_root, args.revision)
    install_local_dependencies(curr_buildbot_root, test_buildbot_root)
    run_test(test_buildbot_root)

    if not args.dont_clean:
        shutil.rmtree(test_buildbot_root)


if __name__ == '__main__':
    main()
