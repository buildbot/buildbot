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

from __future__ import absolute_import
from __future__ import print_function

# Method to add build step taken from here
# https://seasonofcode.com/posts/how-to-add-custom-build-steps-and-commands-to-setuppy.html
import datetime
import distutils.cmd
import os
import re
import subprocess
import sys
import json
import shutil
from distutils.version import LooseVersion
from subprocess import PIPE
from subprocess import STDOUT
from subprocess import Popen
import setuptools.command.build_py
import setuptools.command.egg_info
from setuptools import setup

old_listdir = os.listdir


def listdir(path):
    # patch listdir to avoid looking into node_modules
    l = old_listdir(path)
    if "node_modules" in l:
        l.remove("node_modules")
    return l
os.listdir = listdir


def check_output(cmd):
    """Version of check_output which does not throw error"""
    popen = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    out = popen.communicate()[0].strip()
    if not isinstance(out, str):
        out = out.decode(sys.stdout.encoding)
    return out


def gitDescribeToPep440(version):
    # git describe produce version in the form: v0.9.8-20-gf0f45ca
    # where 20 is the number of commit since last release, and gf0f45ca is the short commit id preceded by 'g'
    # we parse this a transform into a pep440 release version 0.9.9.dev20 (increment last digit and add dev before 20)

    VERSION_MATCH = re.compile(
        r'(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(\.post(?P<post>\d+))?(-(?P<dev>\d+))?(-g(?P<commit>.+))?')
    v = VERSION_MATCH.search(version)
    if v:
        major = int(v.group('major'))
        minor = int(v.group('minor'))
        patch = int(v.group('patch'))
        if v.group('dev'):
            patch += 1
            dev = int(v.group('dev'))
            return "{}.{}.{}-dev{}".format(major, minor, patch, dev)
        if v.group('post'):
            return "{}.{}.{}.post{}".format(major, minor, patch, v.group('post'))
        return "{}.{}.{}".format(major, minor, patch)

    return v


def mTimeVersion(init_file):
    cwd = os.path.dirname(os.path.abspath(init_file))
    m = 0
    for root, dirs, files in os.walk(cwd):
        for f in files:
            m = max(os.path.getmtime(os.path.join(root, f)), m)
    d = datetime.datetime.fromtimestamp(m)
    return d.strftime("%Y.%m.%d")


def getVersionFromArchiveId(git_archive_id='$Format:%ct %d$'):
    """ Extract the tag if a source is from git archive.

        When source is exported via `git archive`, the git_archive_id init value is modified
        and placeholders are expanded to the "archived" revision:

            %ct: committer date, UNIX timestamp
            %d: ref names, like the --decorate option of git-log

        See man gitattributes(5) and git-log(1) (PRETTY FORMATS) for more details.
    """
    # mangle the magic string to make sure it is not replaced by git archive
    if not git_archive_id.startswith('$For''mat:'):
        # source was modified by git archive, try to parse the version from
        # the value of git_archive_id

        match = re.search(r'tag:\s*v([^,)]+)', git_archive_id)
        if match:
            # archived revision is tagged, use the tag
            return gitDescribeToPep440(match.group(1))

        # archived revision is not tagged, use the commit date
        tstamp = git_archive_id.strip().split()[0]
        d = datetime.datetime.fromtimestamp(int(tstamp))
        return d.strftime('%Y.%m.%d')
    return None


def getVersion(init_file):
    """
    Return BUILDBOT_VERSION environment variable, content of VERSION file, git
    tag or 'latest'
    """

    try:
        return os.environ['BUILDBOT_VERSION']
    except KeyError:
        pass

    try:
        cwd = os.path.dirname(os.path.abspath(init_file))
        fn = os.path.join(cwd, 'VERSION')
        with open(fn) as f:
            return f.read().strip()
    except IOError:
        pass

    version = getVersionFromArchiveId()
    if version is not None:
        return version

    try:
        p = Popen(['git', 'describe', '--tags', '--always'],
                  stdout=PIPE, stderr=STDOUT, cwd=cwd)
        out = p.communicate()[0]

        if (not p.returncode) and out:
            v = gitDescribeToPep440(str(out))
            if v:
                return v
    except OSError:
        pass

    try:
        # if we really can't find the version, we use the date of modification of the most recent file
        # docker hub builds cannot use git describe
        return mTimeVersion(init_file)
    except Exception:
        # bummer. lets report something
        return "latest"


# JS build strategy:
#
# Obviously, building javascript with setuptools is not really something supported initially
#
# The goal of this hack are:
# - override the distutils command to insert our js build
# - has very small setup.py
#
# from buildbot_pkg import setup_www
#
# setup_www(
#   ...
#    packages=["buildbot_myplugin"]
# )
#
# We need to override the first command done, so that source tree is populated very soon,
# as well as version is found from git tree or "VERSION" file
#
# This supports following setup.py commands:
#
# - develop, via egg_info
# - install, via egg_info
# - sdist, via egg_info
# - bdist_wheel, via build
# This is why we override both egg_info and build, and the first run build
# the js.

def uglify(all_js, mangle=True):
    # buildbot code depends on https://github.com/olov/ng-annotate
    # to add dependency injection annotation
    # if we don't use ng-annotate, we can't use a minimizer which mangle function names
    cmd = ['uglifyjs', '-c']
    if mangle:
        cmd.append('-m')
    p = Popen(cmd,
              stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    return p.communicate(input=all_js)[0]


class BuildJsCommand(distutils.cmd.Command):
    """A custom command to run JS build."""

    description = 'run JS build'
    already_run = False

    def initialize_options(self):
        """Set default values for options."""

    def finalize_options(self):
        """Post-process options."""

    def build_with_node(self, has_gulp, has_webpack):
        npm_bin = check_output("npm bin").strip()
        yarn_version = check_output("yarn --version")
        npm_version = check_output("npm -v")
        print("yarn:", yarn_version, "npm: ",
              npm_version)
        assert npm_version != "", "need nodejs and npm installed in current PATH"
        assert LooseVersion(npm_version) >= LooseVersion(
            "1.4"), "npm < 1.4 (%s)" % (npm_version)

        commands = []

        # if we find yarn, then we use it as it is much faster
        if yarn_version != "":
            commands.append(['yarn', 'install', '--pure-lockfile'])
        else:
            commands.append(['npm', 'install'])

        if has_gulp:
            commands.append(
                [os.path.join(npm_bin, "gulp"), 'prod', '--notests'])
        elif has_webpack:
            commands.append([os.path.join(npm_bin, "webpack"), '-p'])

        shell = bool(os.name == 'nt')

        for command in commands:
            self.announce(
                'Running command: %s' % str(" ".join(command)),
                level=distutils.log.INFO)
            subprocess.call(command, shell=shell)

    def build_with_python(self, package):
        from buildbot_pkg.pyjade import simple_convert as jade_convert
        static = os.path.join(package, 'static')
        shutil.rmtree(static, True)
        os.mkdir(static)
        os.mkdir(os.path.join(static, 'img'))
        os.mkdir(os.path.join(static, 'fonts'))
        TEMPLATE_HEADER = 'angular.module("app").run(["$templateCache", function($templateCache) {\n'
        TEMPLATE_BODY = '$templateCache.put("{url}",{content});\n'
        TEMPLATE_FOOTER = '}]);'
        all_modules = ""
        all_coffee = ""
        all_templates = ""
        all_less = ""
        # walk the source dir to find all interresting files
        for root, dirs, files in os.walk("src", topdown=True):
            for name in files:
                fn = os.path.join(root, name)
                # find all coffee files, which are not tests
                if name.endswith(".coffee") and not name.endswith(".spec.coffee"):
                    with open(fn) as f:
                        content = f.read()
                    # if the file is a module definition, it must be placed first
                    if name.endswith(".module.coffee"):
                        all_modules += content + "\n"
                    else:
                        all_coffee += content + "\n"
                # convert jades to html
                if name.endswith(".jade"):
                    with open(fn) as f:
                        try:
                            content = jade_convert(f.read())
                        except Exception as e:
                            print("{}: {}".format(fn, str(e)))
                            content = ''
                    if name == "index.jade":
                        with open(os.path.join(static, 'index.html'), 'w') as f:
                            f.write(content)
                    else:
                        all_templates += TEMPLATE_BODY.format(url="views/" + name.replace(".tpl.jade", ".html"),
                                                              content=json.dumps(content))
                # concat the less files
                if name.endswith(".less"):
                    with open(fn) as f:
                        all_less += f.read() + "\n"
                # copy the images
                if name.endswith(".svg") or name.endswith(".png"):
                    shutil.copyfile(fn, os.path.join(static, 'img', name))

        # for some dependencies, we need to copy some datas
        for root, dirs, files in os.walk("libs", topdown=True):
            for name in files:
                fn = os.path.join(root, name)
                # hack to copy the fonts
                if name.endswith(".woff") or name.endswith(".ttf"):
                    shutil.copyfile(fn, os.path.join(static, 'fonts', name))
                # hack to copy the d3 dependency
                if name == "d3.min.js":
                    shutil.copyfile(fn, os.path.join(static, name))

        print("compiling coffee...")
        p = Popen(['coffee', '-c', '-b', '-s'],
                  stdin=PIPE, stdout=PIPE, stderr=STDOUT)
        all_js = p.communicate(input=all_modules + all_coffee)[0]
        all_js += TEMPLATE_HEADER + all_templates + TEMPLATE_FOOTER

        print("compiling less...")
        p = Popen(['lessc', '-'],
                  stdin=PIPE, stdout=PIPE, stderr=STDOUT, cwd="src")
        all_css = p.communicate(input=all_less)[0]

        print("gathering dependencies...")
        # bowerdeps.json contains the list of files we must include
        # the order is important!!
        with open(os.path.join("libs", "bowerdeps.json")) as f:
            bower_deps = json.load(f)
        js_files = bower_deps['js_files']
        all_jsdeps = ""
        for fn in js_files:
            with open(os.path.join(*fn.split('/'))) as f:
                all_jsdeps += f.read() + "\n"
        print("minifying code...")
        # jsdeps first, with full minification, then our scripts, with name mangling disabled
        all_js = uglify(all_jsdeps) + uglify(all_js, mangle=False)
        with open(os.path.join(package, 'static', 'scripts.js'), 'w') as f:
            f.write(all_js)
        with open(os.path.join(package, 'static', 'styles.css'), 'w') as f:
            f.write(all_css)

    def run(self):
        """Run command."""
        if self.already_run:
            return
        package = self.distribution.packages[0]
        has_gulp = os.path.exists("gulpfile.js")
        has_webpack = os.path.exists("webpack.config.js")
        if has_gulp or has_webpack:
            coffee_version = check_output("coffee --version")
            ugligy_version = check_output("uglifyjs --version")
            less_version = check_output("lessc --version")
            if coffee_version != "" and ugligy_version != "" and less_version != "" and not has_webpack:
                self.build_with_python(package)
            else:
                self.build_with_node(has_gulp, has_webpack)
        self.copy_tree(os.path.join(package, 'static'), os.path.join(
            "build", "lib", package, "static"))

        with open(os.path.join("build", "lib", package, "VERSION"), "w") as f:
            f.write(self.distribution.metadata.version)

        with open(os.path.join(package, "VERSION"), "w") as f:
            f.write(self.distribution.metadata.version)

        self.already_run = True


class BuildPyCommand(setuptools.command.build_py.build_py):
    """Custom build command."""

    def run(self):
        self.run_command('build_js')
        setuptools.command.build_py.build_py.run(self)


class EggInfoCommand(setuptools.command.egg_info.egg_info):
    """Custom egginfo command."""

    def run(self):
        self.run_command('build_js')
        setuptools.command.egg_info.egg_info.run(self)


def setup_www_plugin(**kw):
    package = kw['packages'][0]
    if 'version' not in kw:
        kw['version'] = getVersion(os.path.join(package, "__init__.py"))

    setup(cmdclass=dict(
        egg_info=EggInfoCommand,
        build_py=BuildPyCommand,
        build_js=BuildJsCommand),
        **kw)
