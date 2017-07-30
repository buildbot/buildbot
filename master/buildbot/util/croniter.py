#!/usr/bin/python
# Copied from croniter
# https://github.com/taichino/croniter
# Licensed under MIT license
# Pyflakes warnings corrected

# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from future.builtins import range

import re
from datetime import datetime
from time import mktime
from time import time

from dateutil.relativedelta import relativedelta

search_re = re.compile(r'^([^-]+)-([^-/]+)(/(.*))?$')
only_int_re = re.compile(r'^\d+$')
any_int_re = re.compile(r'^\d+')
star_or_int_re = re.compile(r'^(\d+|\*)$')

__all__ = ('croniter',)


class croniter(object):
    RANGES = (
        (0, 59),
        (0, 23),
        (1, 31),
        (1, 12),
        (0, 6),
        (0, 59)
    )
    DAYS = (
        31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31
    )

    ALPHACONV = (
        {},
        {},
        {},
        {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
         'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12},
        {'sun': 0, 'mon': 1, 'tue': 2, 'wed': 3, 'thu': 4, 'fri': 5, 'sat': 0},
        {}
    )

    LOWMAP = (
        {},
        {},
        {0: 1},
        {0: 1},
        {7: 0},
        {},
    )

    bad_length = 'Exactly 5 or 6 columns has to be specified for iterator' \
                 'expression.'

    def __init__(self, expr_format, start_time=time()):
        if isinstance(start_time, datetime):
            start_time = mktime(start_time.timetuple())

        self.cur = start_time
        self.exprs = expr_format.split()

        if len(self.exprs) != 5 and len(self.exprs) != 6:
            raise ValueError(self.bad_length)

        expanded = []

        for i, expr in enumerate(self.exprs):
            e_list = expr.split(',')
            res = []

            while e_list:
                e = e_list.pop()
                t = re.sub(r'^\*(/.+)$', r'%d-%d\1' % (self.RANGES[i][0],
                                                       self.RANGES[i][1]),
                           str(e))
                m = search_re.search(t)

                if m:
                    (low, high, step) = m.group(1), m.group(2), m.group(4) or 1

                    if not any_int_re.search(low):
                        low = self.ALPHACONV[i][low.lower()]

                    if not any_int_re.search(high):
                        high = self.ALPHACONV[i][high.lower()]

                    if (not low or not high or int(low) > int(high) or
                            not only_int_re.search(str(step))):
                        raise ValueError(
                            "[%s] is not acceptable" % expr_format)

                    for j in range(int(low), int(high) + 1):
                        if j % int(step) == 0:
                            e_list.append(j)
                else:
                    if not star_or_int_re.search(t):
                        t = self.ALPHACONV[i][t.lower()]

                    try:
                        t = int(t)
                    except (ValueError, TypeError):
                        pass

                    if t in self.LOWMAP[i]:
                        t = self.LOWMAP[i][t]

                    if t != '*' and (int(t) < self.RANGES[i][0] or
                                     int(t) > self.RANGES[i][1]):
                        raise ValueError(
                            "[%s] is not acceptable, out of range" % expr_format)

                    res.append(t)

            res.sort()
            expanded.append(
                ['*'] if (len(res) == 1 and res[0] == '*') else res)
        self.expanded = expanded

    def get_next(self, ret_type=float):
        return self._get_next(ret_type, is_prev=False)

    def get_prev(self, ret_type=float):
        return self._get_next(ret_type, is_prev=True)

    def _get_next(self, ret_type=float, is_prev=False):
        expanded = self.expanded[:]

        if ret_type not in (float, datetime):
            raise TypeError("Invalid ret_type, only 'float' or 'datetime' "
                            "is acceptable.")

        if expanded[2][0] != '*' and expanded[4][0] != '*':
            bak = expanded[4]
            expanded[4] = ['*']
            t1 = self._calc(self.cur, expanded, is_prev)
            expanded[4] = bak
            expanded[2] = ['*']

            t2 = self._calc(self.cur, expanded, is_prev)
            if not is_prev:
                result = t1 if t1 < t2 else t2
            else:
                result = t1 if t1 > t2 else t2
        else:
            result = self._calc(self.cur, expanded, is_prev)
        self.cur = result

        if ret_type == datetime:
            result = datetime.fromtimestamp(result)
        return result

    def _calc(self, now, expanded, is_prev):
        if is_prev:
            nearest_diff_method = self._get_prev_nearest_diff
            sign = -1
        else:
            nearest_diff_method = self._get_next_nearest_diff
            sign = 1

        offset = 1 if len(expanded) == 6 else 60
        dst = now = datetime.fromtimestamp(now + sign * offset)

        # BUILDBOT: unused 'day' omitted due to pyflakes warning
        month, year = dst.month, dst.year
        current_year = now.year
        DAYS = self.DAYS

        def proc_month(d):
            if expanded[3][0] != '*':
                diff_month = nearest_diff_method(d.month, expanded[3], 12)
                days = DAYS[month - 1]
                if month == 2 and self.is_leap(year):
                    days += 1

                reset_day = days if is_prev else 1

                if diff_month is not None and diff_month != 0:
                    if is_prev:
                        d += relativedelta(months=diff_month)
                    else:
                        d += relativedelta(months=diff_month, day=reset_day,
                                           hour=0, minute=0, second=0)
                    return True, d
            return False, d

        def proc_day_of_month(d):
            if expanded[2][0] != '*':
                days = DAYS[month - 1]
                if month == 2 and self.is_leap(year):
                    days += 1

                diff_day = nearest_diff_method(d.day, expanded[2], days)

                if diff_day is not None and diff_day != 0:
                    if is_prev:
                        d += relativedelta(days=diff_day)
                    else:
                        d += relativedelta(days=diff_day,
                                           hour=0, minute=0, second=0)
                    return True, d
            return False, d

        def proc_day_of_week(d):
            if expanded[4][0] != '*':
                diff_day_of_week = nearest_diff_method(
                    d.isoweekday() % 7, expanded[4], 7)
                if diff_day_of_week is not None and diff_day_of_week != 0:
                    if is_prev:
                        d += relativedelta(days=diff_day_of_week)
                    else:
                        d += relativedelta(days=diff_day_of_week,
                                           hour=0, minute=0, second=0)
                    return True, d
            return False, d

        def proc_hour(d):
            if expanded[1][0] != '*':
                diff_hour = nearest_diff_method(d.hour, expanded[1], 24)
                if diff_hour is not None and diff_hour != 0:
                    if is_prev:
                        d += relativedelta(hours=diff_hour)
                    else:
                        d += relativedelta(hours=diff_hour, minute=0, second=0)
                    return True, d
            return False, d

        def proc_minute(d):
            if expanded[0][0] != '*':
                diff_min = nearest_diff_method(d.minute, expanded[0], 60)
                if diff_min is not None and diff_min != 0:
                    if is_prev:
                        d += relativedelta(minutes=diff_min)
                    else:
                        d += relativedelta(minutes=diff_min, second=0)
                    return True, d
            return False, d

        def proc_second(d):
            if len(expanded) == 6:
                if expanded[5][0] != '*':
                    diff_sec = nearest_diff_method(d.second, expanded[5], 60)
                    if diff_sec is not None and diff_sec != 0:
                        d += relativedelta(seconds=diff_sec)
                        return True, d
            else:
                d += relativedelta(second=0)
            return False, d

        if is_prev:
            procs = [proc_second,
                     proc_minute,
                     proc_hour,
                     proc_day_of_week,
                     proc_day_of_month,
                     proc_month]
        else:
            procs = [proc_month,
                     proc_day_of_month,
                     proc_day_of_week,
                     proc_hour,
                     proc_minute,
                     proc_second]

        while abs(year - current_year) <= 1:
            next = False
            for proc in procs:
                (changed, dst) = proc(dst)
                if changed:
                    next = True
                    break
            if next:
                continue
            return mktime(dst.timetuple())

        raise("failed to find prev date")

    def _get_next_nearest(self, x, to_check):
        small = [item for item in to_check if item < x]
        large = [item for item in to_check if item >= x]
        large.extend(small)
        return large[0]

    def _get_prev_nearest(self, x, to_check):
        small = [item for item in to_check if item <= x]
        large = [item for item in to_check if item > x]
        small.reverse()
        large.reverse()
        small.extend(large)
        return small[0]

    def _get_next_nearest_diff(self, x, to_check, range_val):
        for i, d in enumerate(to_check):
            if d >= x:
                return d - x
        return to_check[0] - x + range_val

    def _get_prev_nearest_diff(self, x, to_check, range_val):
        candidates = to_check[:]
        candidates.reverse()
        for d in candidates:
            if d <= x:
                return d - x
        return (candidates[0]) - x - range_val

    def is_leap(self, year):
        return year % 400 == 0 or (year % 4 == 0 and year % 100 != 0)


if __name__ == '__main__':

    base = datetime(2010, 1, 25)
    itr = croniter('0 0 1 * *', base)
    n1 = itr.get_next(datetime)
    print(n1)
