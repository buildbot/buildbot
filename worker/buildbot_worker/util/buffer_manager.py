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

    def join_line_info(self, previous_line_info, new_line_info):
        previous_line_text = previous_line_info[0]
        len_previous_line_text = len(previous_line_text)
        new_line_text = previous_line_text + new_line_info[0]

        new_line_indexes = previous_line_info[1]
        for index in new_line_info[1]:
            new_line_indexes.append(len_previous_line_text + index)

        new_time_indexes = previous_line_info[2]
        for time in new_line_info[2]:
            new_time_indexes.append(time)

        return (new_line_text, new_line_indexes, new_time_indexes)

    def buffered_append_maybe_join_lines(self, logname, msg_data):
        # if logname is the same as before: join message's line information with previous one
        if len(self._buffered) > 0 and self._buffered[-1][0] == logname:
            # different data format, when logname is 'log'
            # compare a log of first element of the data
            # second element is information about line
            # e.g. data = ('test_log', ('hello\n', [5], [0.0]))
            udpate_output = self._buffered[-1][1]
            if logname == "log":
                if udpate_output[0] == msg_data[0]:
                    joined_line_info = self.join_line_info(udpate_output[1], msg_data[1])
                    self._buffered[-1] = (logname, (msg_data[0], joined_line_info))
                    return
            else:
                joined_line_info = self.join_line_info(udpate_output, msg_data)
                self._buffered[-1] = (logname, joined_line_info)
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
            if logname == "log":
                # different data format, when logname is 'log'
                # e.g. data = ('test_log', ('hello\n', [5], [0.0]))
                len_data = len(data[1][0]) + 8 * (len(data[1][1]) + len(data[1][2]))
            else:
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

        if logname == "log":
            log = data[0]
            data = data[1]

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
                line_info = (data[0][pos_substring_start:pos_substring_end],
                             [index - pos_substring_start for index in data[1][pos_start:pos_end]],
                             data[2][pos_start: pos_end])
            else:
                line_info = (data[0][:pos_substring_end],
                             data[1][:pos_end],
                             data[2][:pos_end])

            if logname == "log":
                msg_data = (log, line_info)
            else:
                msg_data = line_info

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
