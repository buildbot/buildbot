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

        replacements = [
            ('guanlecoja-ui',
             'link:' + os.path.join(curr_buildbot_root, 'www/data_module')),
            ('buildbot-data-js',
             'link:' + os.path.join(curr_buildbot_root, 'www/guanlecoja-ui')),
            ('buildbot-build-common',
             'link:' + os.path.join(curr_buildbot_root, 'www/build_common')),
        ]

        for dep_key in ['dependencies', 'devDependencies']:
            if dep_key not in contents:
                continue

            deps = contents[dep_key]
            for package, target in replacements:
                if package in deps:
                    deps[package] = target

        with open(package_json_path, 'w') as out_f:
            json.dump(contents, out_f, indent=4, sort_keys=True)


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
