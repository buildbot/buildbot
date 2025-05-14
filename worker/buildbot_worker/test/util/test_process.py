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

from __future__ import annotations

from twisted.trial import unittest

from buildbot_worker.util import process


class TestComputeEnviron(unittest.TestCase):
    def setUp(self) -> None:
        pass

    def test_none_environ(self) -> None:
        result = process.compute_environ(None, {'PATH': '/usr/bin:/bin'}, ';')
        self.assertEqual(result, {'PATH': '/usr/bin:/bin'})

    def test_empty_environ(self) -> None:
        result = process.compute_environ({}, {'PATH': '/usr/bin:/bin'}, ';')
        self.assertEqual(result, {'PATH': '/usr/bin:/bin'})

    def test_empty_string_value(self) -> None:
        result = process.compute_environ({'EMPTY': ''}, {'PATH': '/usr/bin'}, ';')
        self.assertEqual(result, {'EMPTY': '', 'PATH': '/usr/bin'})

    def test_list_value(self) -> None:
        result = process.compute_environ(
            {'PATH': ['/usr/local/bin', '/opt/bin']}, {'PYTHONPATH': '/usr/lib/python'}, ';'
        )
        self.assertEqual(
            result, {'PATH': '/usr/local/bin;/opt/bin', 'PYTHONPATH': '/usr/lib/python'}
        )

    def test_empty_list_value(self) -> None:
        result = process.compute_environ({'PATH': []}, {'PYTHONPATH': '/lib/python'}, ';')
        self.assertEqual(result, {'PATH': '', 'PYTHONPATH': '/lib/python'})

    def test_pythonpath_append(self) -> None:
        result = process.compute_environ(
            {'PYTHONPATH': '/custom/path'}, {'PYTHONPATH': '/usr/lib/python'}, ';'
        )
        self.assertEqual(result, {'PYTHONPATH': '/custom/path;/usr/lib/python'})

    def test_env_var_substitution(self) -> None:
        result = process.compute_environ(
            {'NEW_PATH': '${PATH}:${OTHER_VAR}'},
            {'PATH': '/usr/bin:/bin', 'OTHER_VAR': 'value'},
            ';',
        )
        self.assertEqual(
            result,
            {'NEW_PATH': '/usr/bin:/bin:value', 'PATH': '/usr/bin:/bin', 'OTHER_VAR': 'value'},
        )

    def test_none_value_removes_var(self) -> None:
        result = process.compute_environ(
            {'OTHER_VAR': None}, {'OTHER_VAR': 'value', 'PATH': '/usr/bin'}, ';'
        )
        self.assertEqual(result, {'PATH': '/usr/bin'})

    def test_invalid_value_type(self) -> None:
        with self.assertRaises(RuntimeError) as cm:
            process.compute_environ(
                # test wrong type handling
                {'INVALID': 123},  # type: ignore[dict-item]
                {'PATH': '/usr/bin'},
                ';',
            )
        self.assertIn("'env' values must be strings or lists", str(cm.exception))

    def test_merge_with_os_environ(self) -> None:
        result = process.compute_environ({'NEW_VAR': 'new_value'}, {'PATH': '/usr/bin:/bin'}, ';')
        self.assertEqual(result, {'NEW_VAR': 'new_value', 'PATH': '/usr/bin:/bin'})

    def test_nonexistent_var_substitution(self) -> None:
        result = process.compute_environ({'NEW_VAR': '${NONEXISTENT}'}, {'PATH': '/usr/bin'}, ';')
        self.assertEqual(result, {'NEW_VAR': '', 'PATH': '/usr/bin'})

    def test_special_chars(self) -> None:
        result = process.compute_environ(
            {'NEW_VAR': '${SPECIAL}'}, {'SPECIAL': 'value with spaces and $ymbols!@#'}, ';'
        )
        self.assertEqual(
            result,
            {
                'NEW_VAR': 'value with spaces and $ymbols!@#',
                'SPECIAL': 'value with spaces and $ymbols!@#',
            },
        )

    def test_unicode_chars(self) -> None:
        result = process.compute_environ(
            {'NEW_VAR': '${UNICODE}'}, {'UNICODE': 'café', 'PATH': '/usr/bin'}, ';'
        )
        self.assertEqual(result, {'NEW_VAR': 'café', 'UNICODE': 'café', 'PATH': '/usr/bin'})
