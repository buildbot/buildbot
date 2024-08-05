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
from twisted.trial import unittest

from buildbot.process.properties import Interpolate
from buildbot.steps.configurable import BuildbotCiYml
from buildbot.steps.configurable import evaluate_condition
from buildbot.steps.configurable import parse_env_string
from buildbot.steps.shell import ShellCommand


class TestParseEnvString(unittest.TestCase):
    @parameterized.expand([
        ('single', 'ABC=1', {'ABC': '1'}),
        ('multiple', 'ABC=1 EFG=2', {'ABC': '1', 'EFG': '2'}),
        ('multiple_empty_quotes', 'ABC=\'\' EFG=2', {'ABC': '', 'EFG': '2'}),
        ('multiple_empty_double_quotes', 'ABC="" EFG=2', {'ABC': '', 'EFG': '2'}),
        ('multiple_single_quotes', 'ABC=\'1\' EFG=2', {'ABC': '1', 'EFG': '2'}),
        ('multiple_double_quotes', 'ABC="1" EFG=2', {'ABC': '1', 'EFG': '2'}),
        ('multiple_with_equals_in_value', 'ABC=1=2 EFG=2', {'ABC': '1=2', 'EFG': '2'}),
        (
            'multiple_with_equals_in_value_single_quotes',
            'ABC=\'1=2\' EFG=2',
            {'ABC': '1=2', 'EFG': '2'},
        ),
        (
            'multiple_with_equals_in_value_double_quotes',
            'ABC="1=2" EFG=2',
            {'ABC': '1=2', 'EFG': '2'},
        ),
        (
            'multiple_with_space_in_value_single_quotes',
            'ABC=\'1 2\' EFG=2',
            {'ABC': '1 2', 'EFG': '2'},
        ),
        (
            'multiple_with_space_in_value_double_quotes',
            'ABC="1 2" EFG=2',
            {'ABC': '1 2', 'EFG': '2'},
        ),
    ])
    def test_one(self, name, value, expected):
        self.assertEqual(parse_env_string(value), expected)

    @parameterized.expand([
        ('dot', 'ABC=1.0', {'ABC': '1.0'}),
        ('dash', 'ABC=1-0', {'ABC': '1-0'}),
        ('plus', 'ABC=1+0', {'ABC': '1+0'}),
        ('multiply', 'ABC=1*0', {'ABC': '1*0'}),
        ('tilde', 'ABC=1~0', {'ABC': '1~0'}),
        ('hat', 'ABC=1^0', {'ABC': '1^0'}),
        ('comma', 'ABC=1,0', {'ABC': '1,0'}),
        ('colon', 'ABC=1:0', {'ABC': '1:0'}),
        ('slash', 'ABC=1/0', {'ABC': '1/0'}),
        ('pipe', 'ABC=1|0', {'ABC': '1|0'}),
        ('excl_mark', 'ABC=1!0', {'ABC': '1!0'}),
        ('question_mark', 'ABC=1?0', {'ABC': '1?0'}),
        ('left_paren', 'ABC=1(0', {'ABC': '1(0'}),
        ('right_paren', 'ABC=1)0', {'ABC': '1)0'}),
        ('left_brace', 'ABC=1[0', {'ABC': '1[0'}),
        ('right_brace', 'ABC=1]0', {'ABC': '1]0'}),
        ('left_curly_brace', 'ABC=1{0', {'ABC': '1{0'}),
        ('right_curly_brace', 'ABC=1}0', {'ABC': '1}0'}),
        ('left_angled_brace', 'ABC=1<0', {'ABC': '1<0'}),
        ('right_angled_brace', 'ABC=1>0', {'ABC': '1>0'}),
    ])
    def test_special_characters(self, name, value, expected):
        self.assertEqual(parse_env_string(value), expected)

    def test_global_overridden(self):
        self.assertEqual(
            parse_env_string('K1=VE1 K2=VE2', {'K2': 'VG1', 'K3': 'VG3'}),
            {'K1': 'VE1', 'K2': 'VE2', 'K3': 'VG3'},
        )


class TestEvaluateCondition(unittest.TestCase):
    def test_bool(self):
        self.assertTrue(evaluate_condition('True', {}))
        self.assertFalse(evaluate_condition('False', {}))

    def test_string_empty(self):
        self.assertFalse(evaluate_condition('VALUE', {'VALUE': ''}))
        self.assertTrue(evaluate_condition('VALUE', {'VALUE': 'abc'}))

    def test_string_equal(self):
        self.assertTrue(evaluate_condition('VALUE == "a"', {'VALUE': 'a'}))
        self.assertFalse(evaluate_condition('VALUE == "a"', {'VALUE': 'b'}))

    def test_string_in_tuple(self):
        cond = 'VALUE in ("a", "b", "c", "d")'
        self.assertTrue(evaluate_condition(cond, {'VALUE': 'a'}))
        self.assertFalse(evaluate_condition(cond, {'VALUE': 'not'}))

    def test_string_not_in_tuple(self):
        cond = 'VALUE not in ("a", "b", "c", "d")'
        self.assertFalse(evaluate_condition(cond, {'VALUE': 'a'}))
        self.assertTrue(evaluate_condition(cond, {'VALUE': 'not'}))


class TestLoading(unittest.TestCase):
    def test_single_script(self):
        c = BuildbotCiYml.load_from_str("""
        script:
            - echo success
        """)
        self.assertEqual(
            c.script_commands,
            {
                'before_install': [],
                'install': [],
                'after_install': [],
                'before_script': [],
                'script': ['echo success'],
                'after_script': [],
            },
        )

    def test_single_script_interpolated_no_replacement(self):
        c = BuildbotCiYml.load_from_str("""
        script:
            - !i echo success
        """)
        self.assertEqual(
            c.script_commands,
            {
                'before_install': [],
                'install': [],
                'after_install': [],
                'before_script': [],
                'script': [Interpolate("echo success")],
                'after_script': [],
            },
        )

    def test_single_script_interpolated_with_replacement(self):
        c = BuildbotCiYml.load_from_str("""
        script:
            - !i echo "%(prop:name)s"
        """)
        self.assertEqual(
            c.script_commands,
            {
                'before_install': [],
                'install': [],
                'after_install': [],
                'before_script': [],
                'script': [Interpolate("echo %(prop:name)s")],
                'after_script': [],
            },
        )

    def test_single_script_dict_interpolate_with_replacement(self):
        c = BuildbotCiYml.load_from_str("""
        script:
            - title: mytitle
            - cmd: [ "echo", !i "%(prop:name)s" ]
        """)
        self.assertEqual(
            c.script_commands,
            {
                'before_install': [],
                'install': [],
                'after_install': [],
                'before_script': [],
                'script': [{'title': 'mytitle'}, {'cmd': ['echo', Interpolate('%(prop:name)s')]}],
                'after_script': [],
            },
        )

    def test_multiple_scripts(self):
        c = BuildbotCiYml.load_from_str("""
        script:
            - echo success
            - echo success2
            - echo success3
        """)
        self.assertEqual(
            c.script_commands,
            {
                'before_install': [],
                'install': [],
                'after_install': [],
                'before_script': [],
                'script': ['echo success', 'echo success2', 'echo success3'],
                'after_script': [],
            },
        )

    def test_script_with_step(self):
        c = BuildbotCiYml.load_from_str("""
        script:
            - !ShellCommand
              command: "echo success"
        """)
        self.assertEqual(
            c.script_commands,
            {
                'before_install': [],
                'install': [],
                'after_install': [],
                'before_script': [],
                'script': [ShellCommand(command='echo success')],
                'after_script': [],
            },
        )

    def test_matrix_include_simple(self):
        m = BuildbotCiYml.load_matrix(
            {'matrix': {'include': [{'env': 'ABC=10'}, {'env': 'ABC=11'}, {'env': 'ABC=12'}]}}, {}
        )
        self.assertEqual(
            m, [{'env': {'ABC': '10'}}, {'env': {'ABC': '11'}}, {'env': {'ABC': '12'}}]
        )

    def test_matrix_include_global(self):
        m = BuildbotCiYml.load_matrix(
            {'matrix': {'include': [{'env': 'ABC=10'}, {'env': 'ABC=11'}, {'env': 'ABC=12'}]}},
            {'GLOBAL': 'GV'},
        )
        self.assertEqual(
            m,
            [
                {'env': {'ABC': '10', 'GLOBAL': 'GV'}},
                {'env': {'ABC': '11', 'GLOBAL': 'GV'}},
                {'env': {'ABC': '12', 'GLOBAL': 'GV'}},
            ],
        )

    def test_matrix_include_global_with_override(self):
        m = BuildbotCiYml.load_matrix(
            {'matrix': {'include': [{'env': 'ABC=10'}, {'env': 'ABC=11'}, {'env': 'ABC=12'}]}},
            {'ABC': 'GV'},
        )
        self.assertEqual(
            m,
            [
                {'env': {'ABC': '10'}},
                {'env': {'ABC': '11'}},
                {'env': {'ABC': '12'}},
            ],
        )
