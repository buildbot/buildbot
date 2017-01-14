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

from twisted.trial import unittest

from buildbot import config
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.steps import python
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import steps


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

# this is from a run of epydoc against the buildbot source..
epydoc_output = '''\
  [...............
+---------------------------------------------------------------------
| In /home/dustin/code/buildbot/t/buildbot/master/buildbot/
| ec2.py:
| Import failed (but source code parsing was successful).
|     Error: ImportError: No module named boto (line 19)
|
  [....
Warning: Unable to extract the base list for
         twisted.web.resource.EncodingResourceWrapper: Bad dotted name
  [......
+---------------------------------------------------------------------
| In /home/dustin/code/buildbot/t/buildbot/master/buildbot/worker/
| ec2.py:
| Import failed (but source code parsing was successful).
|     Error: ImportError: No module named boto (line 28)
|
  [...........
+---------------------------------------------------------------------
| In /home/dustin/code/buildbot/t/buildbot/master/buildbot/status/
| status_push.py:
| Import failed (but source code parsing was successful).
|     Error: ImportError: No module named status_json (line 40)
|
  [....................<paragraph>Special descriptor for class __provides__</paragraph>
'''


class BuildEPYDoc(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_sample(self):
        self.setupStep(python.BuildEPYDoc())
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['make', 'epydocs'])
            + ExpectShell.log('stdio',
                              stdout=epydoc_output)
            + 1,
        )
        self.expectOutcome(result=FAILURE,
                           state_string='epydoc warn=1 err=3 (failure)')
        return self.runStep()


class PyLint(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_success(self):
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            + ExpectShell.log('stdio',
                              stdout='Your code has been rated at 10/10')
            + python.PyLint.RC_OK)
        self.expectOutcome(result=SUCCESS, state_string='pylint')
        return self.runStep()

    def test_error(self):
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            + ExpectShell.log(
                'stdio',
                stdout=('W: 11: Bad indentation. Found 6 spaces, expected 4\n'
                        'E: 12: Undefined variable \'foo\'\n'))
            + (python.PyLint.RC_WARNING | python.PyLint.RC_ERROR))
        self.expectOutcome(result=FAILURE,
                           state_string='pylint error=1 warning=1 (failure)')
        self.expectProperty('pylint-warning', 1)
        self.expectProperty('pylint-error', 1)
        return self.runStep()

    def test_header_output(self):
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            + ExpectShell.log(
                'stdio',
                header='W: 11: Bad indentation. Found 6 spaces, expected 4\n')
            + 0)
        self.expectOutcome(result=SUCCESS, state_string='pylint')
        return self.runStep()

    def test_failure(self):
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            + ExpectShell.log(
                'stdio',
                stdout=('W: 11: Bad indentation. Found 6 spaces, expected 4\n'
                        'F: 13: something really strange happened\n'))
            + (python.PyLint.RC_WARNING | python.PyLint.RC_FATAL))
        self.expectOutcome(result=FAILURE,
                           state_string='pylint fatal=1 warning=1 (failure)')
        self.expectProperty('pylint-warning', 1)
        self.expectProperty('pylint-fatal', 1)
        return self.runStep()

    def test_failure_zero_returncode(self):
        # Make sure that errors result in a failed step when pylint's
        # return code is 0, e.g. when run through a wrapper script.
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            + ExpectShell.log(
                'stdio',
                stdout=('W: 11: Bad indentation. Found 6 spaces, expected 4\n'
                        'E: 12: Undefined variable \'foo\'\n'))
            + 0)
        self.expectOutcome(result=FAILURE,
                           state_string='pylint error=1 warning=1 (failure)')
        self.expectProperty('pylint-warning', 1)
        self.expectProperty('pylint-error', 1)
        return self.runStep()

    def test_regex_text(self):
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            + ExpectShell.log(
                'stdio',
                stdout=('W: 11: Bad indentation. Found 6 spaces, expected 4\n'
                        'C:  1:foo123: Missing docstring\n'))
            + (python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION))
        self.expectOutcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expectProperty('pylint-warning', 1)
        self.expectProperty('pylint-convention', 1)
        self.expectProperty('pylint-total', 2)
        return self.runStep()

    def test_regex_text_0_24(self):
        # pylint >= 0.24.0 prints out column offsets when using text format
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            + ExpectShell.log(
                'stdio',
                stdout=('W: 11,0: Bad indentation. Found 6 spaces, expected 4\n'
                        'C:  3,10:foo123: Missing docstring\n'))
            + (python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION))
        self.expectOutcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expectProperty('pylint-warning', 1)
        self.expectProperty('pylint-convention', 1)
        self.expectProperty('pylint-total', 2)
        return self.runStep()

    def test_regex_text_131(self):
        # at least pylint 1.3.1 prints out space padded column offsets when
        # using text format
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            + ExpectShell.log(
                'stdio',
                stdout=('W: 11, 0: Bad indentation. Found 6 spaces, expected 4\n'
                        'C:  3,10:foo123: Missing docstring\n'))
            + (python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION))
        self.expectOutcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expectProperty('pylint-warning', 1)
        self.expectProperty('pylint-convention', 1)
        self.expectProperty('pylint-total', 2)
        return self.runStep()

    def test_regex_text_ids(self):
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            + ExpectShell.log(
                'stdio',
                stdout=('W0311: 11: Bad indentation.\n'
                        'C0111:  1:funcName: Missing docstring\n'))
            + (python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION))
        self.expectOutcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expectProperty('pylint-warning', 1)
        self.expectProperty('pylint-convention', 1)
        self.expectProperty('pylint-total', 2)
        return self.runStep()

    def test_regex_text_ids_0_24(self):
        # pylint >= 0.24.0 prints out column offsets when using text format
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            + ExpectShell.log(
                'stdio',
                stdout=('W0311: 11,0: Bad indentation.\n'
                        'C0111:  3,10:foo123: Missing docstring\n'))
            + (python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION))
        self.expectOutcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expectProperty('pylint-warning', 1)
        self.expectProperty('pylint-convention', 1)
        self.expectProperty('pylint-total', 2)
        return self.runStep()

    def test_regex_parseable_ids(self):
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            + ExpectShell.log(
                'stdio',
                stdout=('test.py:9: [W0311] Bad indentation.\n'
                        'test.py:3: [C0111, foo123] Missing docstring\n'))
            + (python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION))
        self.expectOutcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expectProperty('pylint-warning', 1)
        self.expectProperty('pylint-convention', 1)
        self.expectProperty('pylint-total', 2)
        return self.runStep()

    def test_regex_parseable(self):
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            + ExpectShell.log(
                'stdio',
                stdout=('test.py:9: [W] Bad indentation.\n'
                        'test.py:3: [C, foo123] Missing docstring\n'))
            + (python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION))
        self.expectOutcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expectProperty('pylint-warning', 1)
        self.expectProperty('pylint-convention', 1)
        self.expectProperty('pylint-total', 2)
        return self.runStep()

    def test_regex_parseable_131(self):
        """ In pylint 1.3.1, output parseable is deprecated, but looks like
        that, this is also the new recommended format string:
            --msg-template={path}:{line}: [{msg_id}({symbol}), {obj}] {msg}
        """
        self.setupStep(python.PyLint(command=['pylint']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            + ExpectShell.log(
                'stdio',
                stdout=('test.py:9: [W0311(bad-indentation), ] Bad indentation. Found 6 spaces, expected 4\n'
                        'test.py:3: [C0111(missing-docstring), myFunc] Missing function docstring\n'))
            + (python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION))
        self.expectOutcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expectProperty('pylint-warning', 1)
        self.expectProperty('pylint-convention', 1)
        self.expectProperty('pylint-total', 2)
        return self.runStep()


class PyFlakes(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_success(self):
        self.setupStep(python.PyFlakes())
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['make', 'pyflakes'])
            + 0)
        self.expectOutcome(result=SUCCESS, state_string='pyflakes')
        return self.runStep()

    def test_content_in_header(self):
        self.setupStep(python.PyFlakes())
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['make', 'pyflakes'])
            + ExpectShell.log(
                'stdio',
                # don't match pyflakes-like output in the header
                header="foo.py:1: 'bar' imported but unused\n")
            + 0)
        self.expectOutcome(result=0, state_string='pyflakes')
        return self.runStep()

    def test_unused(self):
        self.setupStep(python.PyFlakes())
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['make', 'pyflakes'])
            + ExpectShell.log(
                'stdio',
                stdout="foo.py:1: 'bar' imported but unused\n")
            + 1)
        self.expectOutcome(result=WARNINGS,
                           state_string='pyflakes unused=1 (warnings)')
        self.expectProperty('pyflakes-unused', 1)
        self.expectProperty('pyflakes-total', 1)
        return self.runStep()

    def test_undefined(self):
        self.setupStep(python.PyFlakes())
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['make', 'pyflakes'])
            + ExpectShell.log(
                'stdio',
                stdout="foo.py:1: undefined name 'bar'\n")
            + 1)
        self.expectOutcome(result=FAILURE,
                           state_string='pyflakes undefined=1 (failure)')
        self.expectProperty('pyflakes-undefined', 1)
        self.expectProperty('pyflakes-total', 1)
        return self.runStep()

    def test_redefs(self):
        self.setupStep(python.PyFlakes())
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['make', 'pyflakes'])
            + ExpectShell.log(
                'stdio',
                stdout="foo.py:2: redefinition of unused 'foo' from line 1\n")
            + 1)
        self.expectOutcome(result=WARNINGS,
                           state_string='pyflakes redefs=1 (warnings)')
        self.expectProperty('pyflakes-redefs', 1)
        self.expectProperty('pyflakes-total', 1)
        return self.runStep()

    def test_importstar(self):
        self.setupStep(python.PyFlakes())
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['make', 'pyflakes'])
            + ExpectShell.log(
                'stdio',
                stdout="foo.py:1: 'from module import *' used; unable to detect undefined names\n")
            + 1)
        self.expectOutcome(result=WARNINGS,
                           state_string='pyflakes import*=1 (warnings)')
        self.expectProperty('pyflakes-import*', 1)
        self.expectProperty('pyflakes-total', 1)
        return self.runStep()

    def test_misc(self):
        self.setupStep(python.PyFlakes())
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['make', 'pyflakes'])
            + ExpectShell.log(
                'stdio',
                stdout="foo.py:2: redefinition of function 'bar' from line 1\n")
            + 1)
        self.expectOutcome(result=WARNINGS,
                           state_string='pyflakes misc=1 (warnings)')
        self.expectProperty('pyflakes-misc', 1)
        self.expectProperty('pyflakes-total', 1)
        return self.runStep()


class TestSphinx(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_builddir_required(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          python.Sphinx())

    def test_bad_mode(self):
        self.assertRaises(config.ConfigErrors, lambda: python.Sphinx(
            sphinx_builddir="_build", mode="don't care"))

    def test_success(self):
        self.setupStep(python.Sphinx(sphinx_builddir="_build"))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['sphinx-build', '.', '_build'])
            + ExpectShell.log('stdio',
                              stdout=log_output_success)
            + 0
        )
        self.expectOutcome(result=SUCCESS, state_string="sphinx 0 warnings")
        return self.runStep()

    def test_failure(self):
        self.setupStep(python.Sphinx(sphinx_builddir="_build"))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['sphinx-build', '.', '_build'])
            + ExpectShell.log('stdio',
                              stdout='oh noes!')
            + 1
        )
        self.expectOutcome(result=FAILURE,
                           state_string="sphinx 0 warnings (failure)")
        return self.runStep()

    def test_nochange(self):
        self.setupStep(python.Sphinx(sphinx_builddir="_build"))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['sphinx-build', '.', '_build'])
            + ExpectShell.log('stdio',
                              stdout=log_output_nochange)
            + 0
        )
        self.expectOutcome(result=SUCCESS,
                           state_string="sphinx 0 warnings")
        return self.runStep()

    def test_warnings(self):
        self.setupStep(python.Sphinx(sphinx_builddir="_build"))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['sphinx-build', '.', '_build'])
            + ExpectShell.log('stdio',
                              stdout=log_output_warnings)
            + 0
        )
        self.expectOutcome(result=WARNINGS,
                           state_string="sphinx 2 warnings (warnings)")
        self.expectLogfile("warnings", warnings)
        d = self.runStep()

        def check(_):
            self.assertEqual(self.step.statistics, {'warnings': 2})
        d.addCallback(check)
        return d

    def test_constr_args(self):
        self.setupStep(python.Sphinx(sphinx_sourcedir='src',
                                     sphinx_builddir="bld",
                                     sphinx_builder='css',
                                     sphinx="/path/to/sphinx-build",
                                     tags=['a', 'b'],
                                     defines=dict(
                                         empty=None, t=True, f=False, s="str"),
                                     mode='full'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['/path/to/sphinx-build', '-b', 'css',
                                 '-t', 'a', '-t', 'b', '-D', 'empty',
                                 '-D', 'f=0', '-D', 's=str', '-D', 't=1',
                                 '-E', 'src', 'bld'])
            + ExpectShell.log('stdio',
                              stdout=log_output_success)
            + 0
        )
        self.expectOutcome(result=SUCCESS, state_string="sphinx 0 warnings")
        return self.runStep()
