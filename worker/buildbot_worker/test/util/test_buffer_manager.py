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

from twisted.trial import unittest

from buildbot_worker.test.reactor import TestReactorMixin
from buildbot_worker.util import buffer_manager


class BufferManager(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.results_collected = []
        self.setup_test_reactor()

    def message_consumer(self, msg_data):
        self.results_collected.append(msg_data)

    def assert_sent_messages(self, expected):
        self.assertEqual(self.results_collected, expected)
        self.results_collected = []

    def test_append_message_rc_fits_in_buffer(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 20, 5)

        manager.append("rc", 1)
        self.assert_sent_messages([])

        manager.flush()
        self.assert_sent_messages([[("rc", 1)]])

    def test_append_message_log_in_one_msg(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 40, 5)

        manager.append("stdout", ('12\n', [2], [1.0]))
        self.assert_sent_messages([])

        manager.append("log", ('log_test', ('text\n', [4], [0.0])))
        self.assert_sent_messages([])

        manager.flush()
        self.assert_sent_messages([
            [("stdout", ('12\n', [2], [1.0])), ("log", ('log_test', ('text\n', [4], [0.0])))]
        ])

    def test_append_message_rc_in_one_msg(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 40, 5)

        manager.append("stdout", ('12\n', [2], [1.0]))
        self.assert_sent_messages([])

        manager.append("rc", 1)
        self.assert_sent_messages([])

        manager.flush()
        self.assert_sent_messages([
            [("stdout", ('12\n', [2], [1.0])), ("rc", 1)]
        ])

    def test_append_message_log_exceeds_buffer(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 20, 5)

        manager.append("stdout", ('12\n', [2], [1.0]))
        self.assert_sent_messages([])

        manager.append("log", ('log_test', ('tex\n', [4], [0.0])))
        self.assert_sent_messages([
            [("stdout", ('12\n', [2], [1.0]))]
        ])

        manager.flush()
        self.assert_sent_messages([
            [("log", ('log_test', ('tex\n', [4], [0.0])))]
        ])

    def test_append_message_rc_exceeds_buffer(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 20, 5)

        manager.append("stdout", ('12\n', [2], [1.0]))
        self.assert_sent_messages([])

        manager.append("rc", 1)
        self.assert_sent_messages([
            [("stdout", ('12\n', [2], [1.0]))]
        ])

        manager.flush()
        self.assert_sent_messages([
            [("rc", 1)]
        ])

    def test_append_two_messages_rc_exceeds_buffer(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 15, 5)

        manager.append("rc", 1)
        self.assert_sent_messages([
            [("rc", 1)]
        ])

        manager.append("rc", 0)
        self.assert_sent_messages([
            [("rc", 0)]
        ])

        manager.flush()
        self.assert_sent_messages([])

    def test_append_two_messages_rc_fits_in_buffer(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 40, 5)

        manager.append("rc", 1)
        self.assert_sent_messages([])

        manager.append("rc", 0)
        self.assert_sent_messages([])

        manager.flush()
        self.assert_sent_messages([[("rc", 1), ("rc", 0)]])

    def test_append_message_exceeds_buffer(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 20, 5)

        manager.append("stdout", ('12345\n', [5], [1.0]))
        self.assert_sent_messages([
            [("stdout", ("12345\n", [5], [1.0]))]
        ])

        manager.flush()
        self.assert_sent_messages([])

    def test_append_message_fits_in_buffer(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 18, 5)

        manager.append("stdout", ("1\n", [1], [1.0]))
        self.assert_sent_messages([])

        manager.flush()
        self.assert_sent_messages([
            [("stdout", ("1\n", [1], [1.0]))]
        ])

        # only to see if flush does not send any more messages
        manager.flush()
        self.assert_sent_messages([])

    def test_append_two_messages_exceeds_buffer(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 20, 5)

        manager.append("stdout", ("1\n", [1], [1.0]))
        self.assert_sent_messages([])

        manager.append("stdout", ("22\n", [2], [2.0]))
        self.assert_sent_messages([
            [("stdout", ("1\n", [1], [1.0]))]
        ])

        manager.flush()
        self.assert_sent_messages([
            [('stdout', ('22\n', [2], [2.0]))]
        ])

    def test_append_two_messages_same_logname_log_joined(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 40, 5)

        manager.append("log", ("log_test", ("1\n", [1], [1.0])))
        self.assert_sent_messages([])

        manager.append("log", ("log_test", ("2\n", [1], [2.0])))
        self.assert_sent_messages([])

        manager.flush()
        self.assert_sent_messages([
            [("log", ("log_test", ("1\n2\n", [1, 3], [1.0, 2.0])))]
        ])

    def test_append_two_messages_same_logname_joined(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 40, 5)

        manager.append("stdout", ("1\n", [1], [1.0]))
        self.assert_sent_messages([])

        manager.append("stdout", ("2\n", [1], [2.0]))
        self.assert_sent_messages([])

        manager.flush()
        self.assert_sent_messages([
            [("stdout", ("1\n2\n", [1, 3], [1.0, 2.0]))]
        ])

    def test_append_two_messages_same_logname_log_joined_many_lines(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 80, 5)

        manager.append("log", ("log_test", ("1\n2\n", [1, 3], [1.0, 2.0])))
        self.assert_sent_messages([])

        manager.append("log", ("log_test", ("3\n4\n", [1, 3], [3.0, 4.0])))
        self.assert_sent_messages([])

        manager.flush()
        self.assert_sent_messages([
            [("log", ("log_test", ("1\n2\n3\n4\n", [1, 3, 5, 7], [1.0, 2.0, 3.0, 4.0])))]
        ])

    def test_append_two_messages_same_logname_joined_many_lines(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 80, 5)

        manager.append("stdout", ("1\n2\n", [1, 3], [1.0, 2.0]))
        self.assert_sent_messages([])

        manager.append("stdout", ("3\n4\n", [1, 3], [3.0, 4.0]))
        self.assert_sent_messages([])

        manager.flush()
        self.assert_sent_messages([
            [("stdout", ("1\n2\n3\n4\n", [1, 3, 5, 7], [1.0, 2.0, 3.0, 4.0]))]
        ])

    def test_append_three_messages_not_same_logname_log_not_joined(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 70, 5)

        manager.append("log", ("log_test", ("1\n", [1], [1.0])))
        self.assert_sent_messages([])

        manager.append("log", ("log_test2", ("2\n", [1], [2.0])))
        self.assert_sent_messages([])

        manager.append("log", ("log_test3", ("3\n", [1], [3.0])))
        self.assert_sent_messages([])

        manager.flush()
        self.assert_sent_messages([
            [("log", ("log_test", ("1\n", [1], [1.0]))),
             ("log", ("log_test2", ("2\n", [1], [2.0]))),
             ("log", ("log_test3", ("3\n", [1], [3.0])))]
        ])

    def test_append_three_messages_not_same_logname_not_joined(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 60, 5)

        manager.append("stdout", ("1\n", [1], [1.0]))
        self.assert_sent_messages([])

        manager.append("stderr", ("2\n", [1], [2.0]))
        self.assert_sent_messages([])

        manager.append("stdout", ("3\n", [1], [3.0]))
        self.assert_sent_messages([])

        manager.flush()
        self.assert_sent_messages([
            [("stdout", ("1\n", [1], [1.0])),
             ("stderr", ("2\n", [1], [2.0])),
             ("stdout", ("3\n", [1], [3.0]))]
        ])

    def test_append_two_messages_same_logname_log_exceeds_buffer(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 20, 5)

        manager.append("log", ("log_test", ("1234\n", [4], [1.0])))
        self.assert_sent_messages([
            [("log", ("log_test", ("1234\n", [4], [1.0])))]
        ])

        manager.append("log", ("log_test", ("5678\n", [4], [2.0])))
        self.assert_sent_messages([
            [("log", ("log_test", ("5678\n", [4], [2.0])))]
        ])

        manager.flush()
        self.assert_sent_messages([])

    def test_append_two_messages_same_logname_exceeds_buffer(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 20, 5)

        manager.append("stdout", ("1234\n", [4], [1.0]))
        self.assert_sent_messages([
            [("stdout", ("1234\n", [4], [1.0]))]
        ])

        manager.append("stdout", ("5678\n", [4], [2.0]))
        self.assert_sent_messages([
            [("stdout", ("5678\n", [4], [2.0]))]
        ])

        manager.flush()
        self.assert_sent_messages([])

    def test_append_exceeds_buffer_log_long_line_first_line_too_long(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 20, 5)

        manager.append("log",
                       ("log_test", ("tbe5\nta4\ntbe5\nt3\ntd4\n", [4, 8, 13, 16, 20],
                        [1.0, 2.0, 3.0, 4.0, 5.0])))

        self.assert_sent_messages([
            [("log", ("log_test", ("tbe5\n", [4], [1.0])))],
            [("log", ("log_test", ("ta4\n", [3], [2.0])))],
            [("log", ("log_test", ("tbe5\n", [4], [3.0])))],
            [("log", ("log_test", ("t3\n", [2], [4.0])))],
            [("log", ("log_test", ("td4\n", [3], [5.0])))]
        ])

        manager.flush()
        self.assert_sent_messages([])

    def test_append_exceeds_buffer_long_line_first_line_too_long(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 20, 5)

        manager.append("stdout",
                       ("tbe5\nta4\ntbe5\nt3\ntd4\n", [4, 8, 13, 16, 20],
                        [1.0, 2.0, 3.0, 4.0, 5.0]))

        self.assert_sent_messages([
            [("stdout", ("tbe5\n", [4], [1.0]))],
            [("stdout", ("ta4\n", [3], [2.0]))],
            [("stdout", ("tbe5\n", [4], [3.0]))],
            [("stdout", ("t3\n", [2], [4.0]))],
            [("stdout", ("td4\n", [3], [5.0]))]
        ])

        manager.flush()
        self.assert_sent_messages([])

    def test_append_exceeds_buffer_log_long_line_middle_line_too_long(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 20, 5)

        manager.append("log", ("log_test",
                       ("t3\nta4\ntbe5\nt3\ntd4\n", [2, 6, 11, 14, 18], [1.0, 2.0, 3.0, 4.0, 5.0])))

        self.assert_sent_messages([
            [("log", ("log_test", ("t3\n", [2], [1.0])))],
            [("log", ("log_test", ("ta4\n", [3], [2.0])))],
            [("log", ("log_test", ("tbe5\n", [4], [3.0])))],
            [("log", ("log_test", ("t3\n", [2], [4.0])))],
            [("log", ("log_test", ("td4\n", [3], [5.0])))]
        ])

        manager.flush()
        self.assert_sent_messages([])

    def test_append_exceeds_buffer_long_line_middle_line_too_long(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 20, 5)

        manager.append("stdout",
                       ("t3\nta4\ntbe5\nt3\ntd4\n", [2, 6, 11, 14, 18], [1.0, 2.0, 3.0, 4.0, 5.0]))

        self.assert_sent_messages([
            [("stdout", ("t3\n", [2], [1.0]))],
            [("stdout", ("ta4\n", [3], [2.0]))],
            [("stdout", ("tbe5\n", [4], [3.0]))],
            [("stdout", ("t3\n", [2], [4.0]))],
            [("stdout", ("td4\n", [3], [5.0]))]
        ])

        manager.flush()
        self.assert_sent_messages([])

    def test_append_long_line_log_concatenate(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 60, 5)

        manager.append("log", ("log_test",
                       ("text_text_text_text_text_text_text_text_\nlex\nteym\nte\ntuz\n",
                        [40, 44, 49, 52, 56],
                        [1.0, 2.0, 3.0, 4.0, 5.0])))

        self.assert_sent_messages([
            [("log", ("log_test", ("text_text_text_text_text_text_text_text_\n", [40], [1.0])))],
            [("log", ("log_test", ("lex\nteym\nte\n", [3, 8, 11], [2.0, 3.0, 4.0])))],
            [("log", ("log_test", ("tuz\n", [3], [5.0])))]
        ])

        manager.flush()
        self.assert_sent_messages([])

    def test_append_long_line_concatenate(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 60, 5)

        manager.append("stdout",
                       ("text_text_text_text_text_text_text_text_\nlex\nteym\nte\ntuz\n",
                        [40, 44, 49, 52, 56],
                        [1.0, 2.0, 3.0, 4.0, 5.0]))

        self.assert_sent_messages([
            [("stdout", ("text_text_text_text_text_text_text_text_\n", [40], [1.0]))],
            [("stdout", ("lex\nteym\nte\n", [3, 8, 11], [2.0, 3.0, 4.0]))],
            [("stdout", ("tuz\n", [3], [5.0]))]
        ])

        manager.flush()
        self.assert_sent_messages([])

    def test_append_log_not_fitting_line_after_fitting_line(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 20, 5)

        manager.append("log", ("log_test", ("12\n", [4], [1.0])))
        self.assert_sent_messages([])

        manager.append("log", ("log_test", ("345678\n", [6], [2.0])))
        self.assert_sent_messages([
            [("log", ("log_test", ("12\n", [4], [1.0])))],
            [("log", ("log_test", ("345678\n", [6], [2.0])))]
        ])

        manager.flush()
        self.assert_sent_messages([])

    def test_append_not_fitting_line_after_fitting_line(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 20, 5)

        manager.append("stdout", ("12\n", [4], [1.0]))
        self.assert_sent_messages([])

        manager.append("stdout", ("345678\n", [6], [2.0]))
        self.assert_sent_messages([
            [("stdout", ("12\n", [4], [1.0]))],
            [("stdout", ("345678\n", [6], [2.0]))]
        ])

        manager.flush()
        self.assert_sent_messages([])

    def test_append_timeout_fits_in_buffer_timeout_expires_with_message(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 20, 5)

        manager.append("stdout", ('12\n', [2], [1.0]))
        self.assert_sent_messages([])

        self.reactor.advance(4)
        self.assert_sent_messages([])

        self.reactor.advance(1)
        self.assert_sent_messages([
            [("stdout", ("12\n", [2], [1.0]))]
        ])

        self.reactor.advance(5)
        self.assert_sent_messages([])

        manager.flush()
        self.assert_sent_messages([])

    def test_append_timeout_fits_in_buffer_two_messages_before_timeout_expires(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 40, 5)

        manager.append("stdout", ('12\n', [2], [1.0]))
        self.assert_sent_messages([])

        self.reactor.advance(1)
        manager.append("stdout", ('345\n', [3], [2.0]))
        self.assert_sent_messages([])

        self.reactor.advance(4)
        self.assert_sent_messages([
            [("stdout", ("12\n345\n", [2, 6], [1.0, 2.0]))]
        ])

        self.reactor.advance(5)
        self.assert_sent_messages([])

        manager.flush()
        self.assert_sent_messages([])

    def test_append_timeout_two_messages_timeout_expires_with_single_message(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 40, 5)

        manager.append("stdout", ('12\n', [2], [1.0]))
        self.assert_sent_messages([])

        self.reactor.advance(5)
        self.assert_sent_messages([
            [("stdout", ("12\n", [2], [1.0]))]
        ])

        manager.append("stdout", ('345\n', [3], [2.0]))
        self.assert_sent_messages([])

        self.reactor.advance(5)
        self.assert_sent_messages([
            [("stdout", ("345\n", [3], [2.0]))]
        ])

        manager.flush()
        self.assert_sent_messages([])

    def test_append_timeout_long_line_flushes_short_line_before_timeout(self):
        manager = buffer_manager.BufferManager(self.reactor, self.message_consumer, 20, 5)

        manager.append("stdout", ('12\n', [2], [1.0]))
        self.assert_sent_messages([])

        manager.append("stdout", ('345678\n', [6], [2.0]))
        self.assert_sent_messages([
            [("stdout", ("12\n", [2], [1.0]))],
            [("stdout", ("345678\n", [6], [2.0]))]
        ])

        self.reactor.advance(5)
        self.assert_sent_messages([])

        manager.flush()
        self.assert_sent_messages([])
