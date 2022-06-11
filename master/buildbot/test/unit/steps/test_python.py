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

from parameterized import parameterized

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.steps import python
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import TestBuildStepMixin

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

log_output_warnings_strict = '''\
Running Sphinx v1.0.7
loading pickled environment... done
building [html]: targets for 1 source files that are out of date
updating environment: 0 added, 1 changed, 0 removed
reading sources... [100%] file

Warning, treated as error:
file.rst:18:Literal block expected; none found.
'''

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


class BuildEPYDoc(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_sample(self):
        self.setup_step(python.BuildEPYDoc())
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['make', 'epydocs'])
            .stdout(epydoc_output)
            .exit(1),
        )
        self.expect_outcome(result=FAILURE,
                           state_string='epydoc warn=1 err=3 (failure)')
        return self.run_step()


class PyLint(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    @parameterized.expand([
        ('no_results', True),
        ('with_results', False)
    ])
    def test_success(self, name, store_results):
        self.setup_step(python.PyLint(command=['pylint'], store_results=store_results))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            .stdout('Your code has been rated at 10/10')
            .exit(python.PyLint.RC_OK))
        self.expect_outcome(result=SUCCESS, state_string='pylint')
        if store_results:
            self.expect_test_result_sets([('Pylint warnings', 'code_issue', 'message')])
            self.expect_test_results([])
        return self.run_step()

    @parameterized.expand([
        ('no_results', True),
        ('with_results', False)
    ])
    def test_error(self, name, store_results):
        self.setup_step(python.PyLint(command=['pylint'], store_results=store_results))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            .stdout('W: 11: Bad indentation. Found 6 spaces, expected 4\n'
                    'E: 12: Undefined variable \'foo\'\n')
            .exit((python.PyLint.RC_WARNING | python.PyLint.RC_ERROR)))
        self.expect_outcome(result=FAILURE,
                           state_string='pylint error=1 warning=1 (failure)')
        self.expect_property('pylint-warning', 1)
        self.expect_property('pylint-error', 1)
        if store_results:
            self.expect_test_result_sets([('Pylint warnings', 'code_issue', 'message')])
            # note that no results are submitted for tests where we don't know the location
        return self.run_step()

    def test_header_output(self):
        self.setup_step(python.PyLint(command=['pylint'], store_results=False))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            .log('stdio', header='W: 11: Bad indentation. Found 6 spaces, expected 4\n')
            .exit(0))
        self.expect_outcome(result=SUCCESS, state_string='pylint')
        return self.run_step()

    def test_failure(self):
        self.setup_step(python.PyLint(command=['pylint'], store_results=False))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            .stdout('W: 11: Bad indentation. Found 6 spaces, expected 4\n'
                    'F: 13: something really strange happened\n')
            .exit((python.PyLint.RC_WARNING | python.PyLint.RC_FATAL)))
        self.expect_outcome(result=FAILURE,
                           state_string='pylint fatal=1 warning=1 (failure)')
        self.expect_property('pylint-warning', 1)
        self.expect_property('pylint-fatal', 1)
        return self.run_step()

    def test_failure_zero_returncode(self):
        # Make sure that errors result in a failed step when pylint's
        # return code is 0, e.g. when run through a wrapper script.
        self.setup_step(python.PyLint(command=['pylint'], store_results=False))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            .stdout('W: 11: Bad indentation. Found 6 spaces, expected 4\n'
                    'E: 12: Undefined variable \'foo\'\n')
            .exit(0))
        self.expect_outcome(result=FAILURE,
                           state_string='pylint error=1 warning=1 (failure)')
        self.expect_property('pylint-warning', 1)
        self.expect_property('pylint-error', 1)
        return self.run_step()

    def test_regex_text(self):
        self.setup_step(python.PyLint(command=['pylint'], store_results=False))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            .stdout('W: 11: Bad indentation. Found 6 spaces, expected 4\n'
                    'C:  1:foo123: Missing docstring\n')
            .exit((python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION)))
        self.expect_outcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expect_property('pylint-warning', 1)
        self.expect_property('pylint-convention', 1)
        self.expect_property('pylint-total', 2)
        return self.run_step()

    def test_regex_text_0_24(self):
        # pylint >= 0.24.0 prints out column offsets when using text format
        self.setup_step(python.PyLint(command=['pylint'], store_results=False))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            .stdout('W: 11,0: Bad indentation. Found 6 spaces, expected 4\n'
                    'C:  3,10:foo123: Missing docstring\n')
            .exit((python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION)))
        self.expect_outcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expect_property('pylint-warning', 1)
        self.expect_property('pylint-convention', 1)
        self.expect_property('pylint-total', 2)
        return self.run_step()

    def test_regex_text_1_3_1(self):
        # at least pylint 1.3.1 prints out space padded column offsets when
        # using text format
        self.setup_step(python.PyLint(command=['pylint'], store_results=False))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            .stdout('W: 11, 0: Bad indentation. Found 6 spaces, expected 4\n'
                    'C:  3,10:foo123: Missing docstring\n')
            .exit((python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION)))
        self.expect_outcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expect_property('pylint-warning', 1)
        self.expect_property('pylint-convention', 1)
        self.expect_property('pylint-total', 2)
        return self.run_step()

    @parameterized.expand([
        ('no_results', True),
        ('with_results', False)
    ])
    def test_regex_text_2_0_0(self, name, store_results):
        # pylint 2.0.0 changed default format to include file path
        self.setup_step(python.PyLint(command=['pylint'], store_results=store_results))

        stdout = (
            'test.py:9:4: W0311: Bad indentation. Found 6 spaces, expected 4 (bad-indentation)\n' +
            'test.py:1:0: C0114: Missing module docstring (missing-module-docstring)\n'
        )

        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            .stdout(stdout)
            .exit((python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION)))
        self.expect_outcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expect_property('pylint-warning', 1)
        self.expect_property('pylint-convention', 1)
        self.expect_property('pylint-total', 2)
        if store_results:
            self.expect_test_result_sets([('Pylint warnings', 'code_issue', 'message')])
            self.expect_test_results([
                (1000, 'test.py:9:4: W0311: Bad indentation. Found 6 spaces, expected 4 ' +
                       '(bad-indentation)',
                 None, 'test.py', 9, None),
                (1000, 'test.py:1:0: C0114: Missing module docstring (missing-module-docstring)',
                 None, 'test.py', 1, None),
            ])
        return self.run_step()

    def test_regex_text_2_0_0_invalid_line(self):
        self.setup_step(python.PyLint(command=['pylint'], store_results=False))

        stdout = (
            'test.py:abc:0: C0114: Missing module docstring (missing-module-docstring)\n'
        )

        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            .stdout(stdout)
            .exit(python.PyLint.RC_CONVENTION))
        self.expect_outcome(result=SUCCESS, state_string='pylint')
        self.expect_property('pylint-warning', 0)
        self.expect_property('pylint-convention', 0)
        self.expect_property('pylint-total', 0)
        return self.run_step()

    def test_regex_text_ids(self):
        self.setup_step(python.PyLint(command=['pylint'], store_results=False))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            .stdout('W0311: 11: Bad indentation.\n'
                    'C0111:  1:funcName: Missing docstring\n')
            .exit((python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION)))
        self.expect_outcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expect_property('pylint-warning', 1)
        self.expect_property('pylint-convention', 1)
        self.expect_property('pylint-total', 2)
        return self.run_step()

    def test_regex_text_ids_0_24(self):
        # pylint >= 0.24.0 prints out column offsets when using text format
        self.setup_step(python.PyLint(command=['pylint'], store_results=False))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            .stdout('W0311: 11,0: Bad indentation.\n'
                    'C0111:  3,10:foo123: Missing docstring\n')
            .exit((python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION)))
        self.expect_outcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expect_property('pylint-warning', 1)
        self.expect_property('pylint-convention', 1)
        self.expect_property('pylint-total', 2)
        return self.run_step()

    @parameterized.expand([
        ('no_results', True),
        ('with_results', False)
    ])
    def test_regex_parseable_ids(self, name, store_results):
        self.setup_step(python.PyLint(command=['pylint'], store_results=store_results))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            .stdout('test.py:9: [W0311] Bad indentation.\n'
                    'test.py:3: [C0111, foo123] Missing docstring\n')
            .exit((python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION)))
        self.expect_outcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expect_property('pylint-warning', 1)
        self.expect_property('pylint-convention', 1)
        self.expect_property('pylint-total', 2)
        if store_results:
            self.expect_test_result_sets([('Pylint warnings', 'code_issue', 'message')])
            self.expect_test_results([
                (1000, 'test.py:9: [W0311] Bad indentation.', None, 'test.py', 9, None),
                (1000, 'test.py:3: [C0111, foo123] Missing docstring', None, 'test.py', 3, None),
            ])
        return self.run_step()

    def test_regex_parseable(self):
        self.setup_step(python.PyLint(command=['pylint'], store_results=False))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            .stdout('test.py:9: [W] Bad indentation.\n'
                    'test.py:3: [C, foo123] Missing docstring\n')
            .exit((python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION)))
        self.expect_outcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expect_property('pylint-warning', 1)
        self.expect_property('pylint-convention', 1)
        self.expect_property('pylint-total', 2)
        return self.run_step()

    def test_regex_parseable_1_3_1(self):
        """ In pylint 1.3.1, output parseable is deprecated, but looks like
        that, this is also the new recommended format string:
            --msg-template={path}:{line}: [{msg_id}({symbol}), {obj}] {msg}
        """
        self.setup_step(python.PyLint(command=['pylint'], store_results=False))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['pylint'])
            .stdout('test.py:9: [W0311(bad-indentation), ] '
                    'Bad indentation. Found 6 '
                    'spaces, expected 4\n'
                    'test.py:3: [C0111(missing-docstring), myFunc] Missing '
                    'function docstring\n')
            .exit((python.PyLint.RC_WARNING | python.PyLint.RC_CONVENTION)))
        self.expect_outcome(result=WARNINGS,
                           state_string='pylint convention=1 warning=1 (warnings)')
        self.expect_property('pylint-warning', 1)
        self.expect_property('pylint-convention', 1)
        self.expect_property('pylint-total', 2)
        return self.run_step()


class PyFlakes(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_success(self):
        self.setup_step(python.PyFlakes())
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['make', 'pyflakes'])
            .exit(0))
        self.expect_outcome(result=SUCCESS, state_string='pyflakes')
        return self.run_step()

    def test_content_in_header(self):
        self.setup_step(python.PyFlakes())
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['make', 'pyflakes'])
            # don't match pyflakes-like output in the header
            .log('stdio', header="foo.py:1: 'bar' imported but unused\n")
            .exit(0))
        self.expect_outcome(result=0, state_string='pyflakes')
        return self.run_step()

    def test_unused(self):
        self.setup_step(python.PyFlakes())
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['make', 'pyflakes'])
            .stdout("foo.py:1: 'bar' imported but unused\n")
            .exit(1))
        self.expect_outcome(result=WARNINGS,
                           state_string='pyflakes unused=1 (warnings)')
        self.expect_property('pyflakes-unused', 1)
        self.expect_property('pyflakes-total', 1)
        return self.run_step()

    def test_undefined(self):
        self.setup_step(python.PyFlakes())
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['make', 'pyflakes'])
            .stdout("foo.py:1: undefined name 'bar'\n")
            .exit(1))
        self.expect_outcome(result=FAILURE,
                           state_string='pyflakes undefined=1 (failure)')
        self.expect_property('pyflakes-undefined', 1)
        self.expect_property('pyflakes-total', 1)
        return self.run_step()

    def test_redefs(self):
        self.setup_step(python.PyFlakes())
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['make', 'pyflakes'])
            .stdout("foo.py:2: redefinition of unused 'foo' from line 1\n")
            .exit(1))
        self.expect_outcome(result=WARNINGS,
                           state_string='pyflakes redefs=1 (warnings)')
        self.expect_property('pyflakes-redefs', 1)
        self.expect_property('pyflakes-total', 1)
        return self.run_step()

    def test_importstar(self):
        self.setup_step(python.PyFlakes())
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['make', 'pyflakes'])
            .stdout("foo.py:1: 'from module import *' used; unable to detect undefined names\n")
            .exit(1))
        self.expect_outcome(result=WARNINGS,
                           state_string='pyflakes import*=1 (warnings)')
        self.expect_property('pyflakes-import*', 1)
        self.expect_property('pyflakes-total', 1)
        return self.run_step()

    def test_misc(self):
        self.setup_step(python.PyFlakes())
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['make', 'pyflakes'])
            .stdout("foo.py:2: redefinition of function 'bar' from line 1\n")
            .exit(1))
        self.expect_outcome(result=WARNINGS,
                           state_string='pyflakes misc=1 (warnings)')
        self.expect_property('pyflakes-misc', 1)
        self.expect_property('pyflakes-total', 1)
        return self.run_step()


class TestSphinx(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_builddir_required(self):
        with self.assertRaises(config.ConfigErrors):
            python.Sphinx()

    def test_bad_mode(self):
        with self.assertRaises(config.ConfigErrors):
            python.Sphinx(sphinx_builddir="_build", mode="don't care")

    def test_success(self):
        self.setup_step(python.Sphinx(sphinx_builddir="_build"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['sphinx-build', '.', '_build'])
            .stdout(log_output_success)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="sphinx 0 warnings")
        return self.run_step()

    def test_failure(self):
        self.setup_step(python.Sphinx(sphinx_builddir="_build"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['sphinx-build', '.', '_build'])
            .stdout('oh noes!')
            .exit(1)
        )
        self.expect_outcome(result=FAILURE,
                           state_string="sphinx 0 warnings (failure)")
        return self.run_step()

    def test_strict_warnings(self):
        self.setup_step(python.Sphinx(sphinx_builddir="_build", strict_warnings=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['sphinx-build', '-W', '.', '_build'])
            .stdout(log_output_warnings_strict)
            .exit(1)
        )
        self.expect_outcome(result=FAILURE,
                           state_string="sphinx 1 warnings (failure)")
        return self.run_step()

    def test_nochange(self):
        self.setup_step(python.Sphinx(sphinx_builddir="_build"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['sphinx-build', '.', '_build'])
            .stdout(log_output_nochange)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS,
                           state_string="sphinx 0 warnings")
        return self.run_step()

    @defer.inlineCallbacks
    def test_warnings(self):
        self.setup_step(python.Sphinx(sphinx_builddir="_build"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['sphinx-build', '.', '_build'])
            .stdout(log_output_warnings)
            .exit(0)
        )
        self.expect_outcome(result=WARNINGS,
                           state_string="sphinx 2 warnings (warnings)")
        self.expect_log_file("warnings", warnings)
        yield self.run_step()

        self.assertEqual(self.step.statistics, {'warnings': 2})

    def test_constr_args(self):
        self.setup_step(python.Sphinx(sphinx_sourcedir='src',
                                     sphinx_builddir="bld",
                                     sphinx_builder='css',
                                     sphinx="/path/to/sphinx-build",
                                     tags=['a', 'b'],
                                     strict_warnings=True,
                                     defines=dict(
                                         empty=None, t=True, f=False, s="str"),
                                     mode='full'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['/path/to/sphinx-build', '-b', 'css',
                                 '-t', 'a', '-t', 'b', '-D', 'empty',
                                 '-D', 'f=0', '-D', 's=str', '-D', 't=1',
                                 '-E', '-W', 'src', 'bld'])
            .stdout(log_output_success)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="sphinx 0 warnings")
        return self.run_step()
