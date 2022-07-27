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


class BufferManager:
    def __init__(self, reactor, message_consumer, buffer_size, buffer_timeout):
        self._reactor = reactor
        self._buflen = 0
        self._buffered = []
        self._buffer_size = buffer_size
        self._buffer_timeout = buffer_timeout
        self._send_message_timer = None
        self._message_consumer = message_consumer

    def buffered_append_maybe_join_lines(self, logname, msg_data):
        # if logname is the same as before: join message's information with previous one
        if len(self._buffered) > 0 and self._buffered[-1][0] == logname:
            previous_msg_text = self._buffered[-1][1][0]
            len_previous_msg_text = len(previous_msg_text)

            new_text = previous_msg_text + msg_data[0]

            new_indexes = self._buffered[-1][1][1]
            for index in msg_data[1]:
                new_indexes.append(len_previous_msg_text + index)

            new_times = self._buffered[-1][1][2]
            for time in msg_data[2]:
                new_times.append(time)

            self._buffered[-1] = (logname, (new_text, new_indexes, new_times))
            return

        self._buffered.append((logname, msg_data))

    def setup_timeout(self):
        if not self._send_message_timer:
            self._send_message_timer = self._reactor.callLater(self._buffer_timeout,
                                                               self.send_message_from_buffer)

    def append(self, logname, data):
        # add data to the buffer for logname
        # keep appending to self._buffered until it gets longer than BUFFER_SIZE
        # which requires emptying the buffer by sending the message to the master

        is_log_message = logname in ("log", "stdout", "stderr", "header")

        if not is_log_message:
            len_data = 20
        else:
            # data = (output_lines, positions_new_line_characters, lines_times)
            len_data = len(data[0]) + 8 * (len(data[1]) + len(data[2]))

        space_left = self._buffer_size - self._buflen

        if len_data <= space_left:
            # fills the buffer with short lines
            if not is_log_message:
                self._buffered.append((logname, data))
            else:
                self.buffered_append_maybe_join_lines(logname, data)
            self._buflen += len_data
            self.setup_timeout()
            return

        self.send_message_from_buffer()

        if len_data <= self._buffer_size:
            self._buffered.append((logname, data))
            self._buflen += len_data
            self.setup_timeout()
            return

        if not is_log_message:
            self.send_message([(logname, data)])
            return

        pos_start = 0
        while pos_start < len(data[1]):
            # pos_end: which line is the last to be sent as a message (non-inclusive range)
            pos_end = pos_start + 1

            # Finds the range of lines to be sent:
            # pos_start - inclusive index of first line to be sent
            # pos_end - exclusive index of last line to be sent
            while pos_end <= len(data[1]):
                if pos_start == 0:
                    string_part_size = data[1][pos_end - 1] + 1
                else:
                    string_part_size = data[1][pos_end - 1] - (data[1][pos_start - 1])
                index_list_part_size = (pos_end - pos_start) * 8
                times_list_part_size = (pos_end - pos_start) * 8
                line_size = string_part_size + index_list_part_size + times_list_part_size

                if line_size <= self._buffer_size:
                    pos_end += 1
                else:
                    if pos_end > pos_start + 1:
                        pos_end -= 1
                    break

            if pos_end > len(data[1]):
                # no more lines are left to grab
                pos_end -= 1

            pos_substring_end = data[1][pos_end - 1] + 1
            if pos_start != 0:
                pos_substring_start = data[1][pos_start - 1] + 1
                msg_data = (data[0][pos_substring_start:pos_substring_end],
                            [index - pos_substring_start for index in data[1][pos_start:pos_end]],
                            data[2][pos_start: pos_end])
            else:
                msg_data = (data[0][:pos_substring_end],
                            data[1][:pos_end],
                            data[2][:pos_end])

            self.send_message([(logname, msg_data)])
            pos_start = pos_end

    def send_message_from_buffer(self):
        self.send_message(self._buffered)
        self._buffered = []
        self._buflen = 0

        if self._send_message_timer:
            if self._send_message_timer.active():
                self._send_message_timer.cancel()
            self._send_message_timer = None

    def send_message(self, data_to_send):
        if len(data_to_send) == 0:
            return
        self._message_consumer(data_to_send)

    def flush(self):
        if len(self._buffered) > 0:
            self.send_message_from_buffer()
