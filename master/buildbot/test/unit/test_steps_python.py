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

import mock
from twisted.trial import unittest
from buildbot.steps import python
from buildbot.status.results import WARNINGS, SUCCESS, FAILURE
from buildbot.test.util import steps
from buildbot.test.fake.remotecommand import ExpectShell, Expect
from buildbot.test.fake.remotecommand import ExpectRemoteRef

log_output_success = '''\
Making output directory...
Running Sphinx v1.0.7
loading pickled environment... not yet created
No builder selected, using default: html
building [html]: targets for 24 source files that are out of date
updating environment: 24 added, 0 changed, 0 removed
reading sources... [  4%] index
reading sources... [  8%] manual/cfg-builders
...
copying static files... done
dumping search index... done
dumping object inventory... done
build succeeded.
'''

log_output_nochange = '''\
Running Sphinx v1.0.7
loading pickled environment... done
No builder selected, using default: html
building [html]: targets for 0 source files that are out of date
updating environment: 0 added, 0 changed, 0 removed
looking for now-outdated files... none found
no targets are out of date.
'''

log_output_warnings = '''\
Running Sphinx v1.0.7
loading pickled environment... done
building [html]: targets for 1 source files that are out of date
updating environment: 0 added, 1 changed, 0 removed
reading sources... [100%] file

file.rst:18: (WARNING/2) Literal block expected; none found.

looking for now-outdated files... none found
pickling environment... done
checking consistency... done
preparing documents... done
writing output... [ 50%] index
writing output... [100%] file

index.rst:: WARNING: toctree contains reference to document 'preamble' that \
doesn't have a title: no link will be generated
writing additional files... search
copying static files... done
dumping search index... done
dumping object inventory... done
build succeeded, 2 warnings.'''

warnings = '''\
file.rst:18: (WARNING/2) Literal block expected; none found.
index.rst:: WARNING: toctree contains reference to document 'preamble' that \
doesn't have a title: no link will be generated\
'''

class TestSphinx(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_builddir_required(self):
        self.assertRaises(TypeError, lambda :
                python.Sphinx())

    def test_success(self):
        self.setupStep(python.Sphinx(sphinx_builddir="_build"))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=['sphinx-build', '.', '_build'])
            + ExpectShell.log('stdio',
                stdout=log_output_success)
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["sphinx", "0 warnings"])
        return self.runStep()

    def test_failure(self):
        self.setupStep(python.Sphinx(sphinx_builddir="_build"))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=['sphinx-build', '.', '_build'])
            + ExpectShell.log('stdio',
                stdout='oh noes!')
            + 1
        )
        self.expectOutcome(result=FAILURE, status_text=["sphinx", "0 warnings", "failed"])
        return self.runStep()

    def test_nochange(self):
        self.setupStep(python.Sphinx(sphinx_builddir="_build"))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=['sphinx-build', '.', '_build'])
            + ExpectShell.log('stdio',
                stdout=log_output_nochange)
            + 0
        )
        self.expectOutcome(result=SUCCESS,
                status_text=["sphinx", "0 warnings"])
        return self.runStep()

    def test_warnings(self):
        self.setupStep(python.Sphinx(sphinx_builddir="_build"))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=['sphinx-build', '.', '_build'])
            + ExpectShell.log('stdio',
                stdout=log_output_warnings)
            + 0
        )
        self.expectOutcome(result=WARNINGS,
                status_text=["sphinx", "2 warnings", "warnings"])
        self.expectLogfile("warnings", warnings)
        d = self.runStep()
        def check(_):
            self.assertEqual(self.step_statistics, { 'warnings' : 2 })
        d.addCallback(check)
        return d

    def test_constr_args(self):
        self.setupStep(python.Sphinx(sphinx_sourcedir='src',
                    sphinx_builddir="bld",
                    sphinx_builder='css',
                    sphinx="/path/to/sphinx-build",
                    tags=['a', 'b'],
                    defines=dict(empty=None, t=True, f=False, s="str")))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=['/path/to/sphinx-build', '-b', 'css',
                                 '-t', 'a', '-t', 'b', '-D', 'empty',
                                 '-D', 'f=0', '-D', 's=str', '-D', 't=1',
                                 'src', 'bld'])
            + ExpectShell.log('stdio',
                stdout=log_output_success)
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["sphinx", "0 warnings"])
        return self.runStep()
