#!/usr/bin/python
# Copied from croniter
# https://github.com/taichino/croniter
# Licensed under MIT license
# Pyflakes warnings corrected

# -*- coding: utf-8 -*-

import calendar
import copy
import re
from datetime import datetime
from time import mktime
from time import time

from dateutil.relativedelta import relativedelta

from buildbot.warnings import warn_deprecated

search_re = re.compile(r'^([^-]+)-([^-/]+)(/(.*))?$')
only_int_re = re.compile(r'^\d+$')
any_int_re = re.compile(r'^\d+')

MONTH_ALPHAS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
DAY_OF_WEEK_ALPHAS = {'sun': 0, 'mon': 1, 'tue': 2, 'wed': 3, 'thu': 4, 'fri': 5, 'sat': 6}
ALPHAS = {}
for i in MONTH_ALPHAS, DAY_OF_WEEK_ALPHAS:
    ALPHAS.update(i)
del i
step_search_re = re.compile(r'^([^-]+)-([^-/]+)(/(\d+))?$')

WEEKDAYS_RE_PART = '|'.join(DAY_OF_WEEK_ALPHAS.keys())
MONTHS_RE_PART = '|'.join(MONTH_ALPHAS.keys())
star_or_int_re = re.compile(r'^(\d+|\*)$')
# This regular expression will search for special cases in the day of week
# and months. Expression like 2#3, l3, jan-feb or mon-tue.
# There are 3 groups: pre, he and last.
special_day_of_week_or_month_re = re.compile(
    (r'^(?P<pre>((?P<he>(({WEEKDAYS})(-({WEEKDAYS}))?)').format(WEEKDAYS=WEEKDAYS_RE_PART) +
    (r'|(({MONTHS})(-({MONTHS}))?)|\w+)#)|l)(?P<last>\d+)$').format(MONTHS=MONTHS_RE_PART)
)

__all__ = ('croniter',)


warn_deprecated(
    "3.10.0",
    "buildbot.util.croniter has been deprecated. Use croniter Pypi package as a replacement. "
    "Note that croniter assumes that the input times in UTC timezone whereas "
    "buildbot.util.croniter assumed that the input times are in local timezone."
)


class croniter:
    MONTHS_IN_YEAR = 12
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
        {},  # 0: min
        {},  # 1: hour
        {'l': 'l'},  # 2: day of month
        # 3: month
        copy.deepcopy(MONTH_ALPHAS),
        # 4: day of week
        copy.deepcopy(DAY_OF_WEEK_ALPHAS),
        # command/user
        {}
    )

    DAY_OF_MONTH_FIELD_INDEX = 2
    DAY_OF_WEEK_FIELD_INDEX = 4

    LOWMAP = (
        {},
        {},
        {0: 1},
        {0: 1},
        {7: 0},
        {},
    )

    MAX_VALUE_PER_INDEX = (
        60,
        24,
        31,
        12,
        7,
        60
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
        nth_weekday_of_month = {}

        for index, expr in enumerate(self.exprs):
            expr = expr.lower()
            field_list = expr.split(',')
            res = []

            while field_list:
                field = field_list.pop()
                nth = None
                special_day_of_week_or_month_re_match = special_day_of_week_or_month_re.match(field)

                # Handle special case in the day of week expression: 2#3, l3
                # There are 3 groups: pre, he and last. For 2#3 applies
                # 2 is pre, # is he, 3 is last. For l3 applies l is pre, he is None
                # and 3 is last.
                if index == self.DAY_OF_WEEK_FIELD_INDEX and special_day_of_week_or_month_re_match:
                    field_groups = special_day_of_week_or_month_re_match.groupdict()
                    he = field_groups.get('he', '')
                    last = field_groups.get('last', '')
                    if he:
                        field = he
                        try:
                            nth = int(last)
                            assert 1 <= nth <= 5
                        except (KeyError, ValueError, AssertionError) as err:
                            raise ValueError(
                                f"[{expr_format}] is not acceptable.  Invalid day_of_week "
                                "value: '{nth}'") from err
                    elif last:
                        field = last
                        nth = field_groups['pre']  # 'L'

                # Before matching step_search_re, normalize "*" to "{min}-{max}".
                # Example: in the minute field, "*/5" normalizes to "0-59/5"
                t = re.sub(r'^\*(\/.+)$',
                           fr'{self.RANGES[index][0]}-{self.RANGES[index][1]}\1',
                           field)
                m = step_search_re.search(t)

                if not m:
                    # Before matching step_search_re,
                    # normalize "{start}/{step}" to "{start}-{max}/{step}".
                    # Example: in the minute field, "10/5" normalizes to "10-59/5"
                    t = re.sub(r'^(.+)\/(.+)$',
                               fr'\1-{self.RANGES[index][1]}/\2',
                               field)
                    m = step_search_re.search(t)

                t = re.sub(r'^\*(/.+)$',
                           fr'{self.RANGES[index][0]}-{self.RANGES[index][1]}\1',
                           field)
                m = search_re.search(t)

                if m:
                    (low, high, step) = m.group(1), m.group(2), m.group(4) or 1
                    if index == self.DAY_OF_MONTH_FIELD_INDEX and high == 'l':
                        high = '31'

                    if not any_int_re.search(low):
                        low = self.ALPHACONV[index][low.lower()]

                    if not any_int_re.search(high):
                        high = self.ALPHACONV[index][high.lower()]

                    if (not low or not high or int(low) > int(high) or
                            not only_int_re.search(str(step))):
                        raise ValueError(f"[{expr_format}] is not acceptable")

                    for j in range(int(low), int(high) + 1):
                        if j % int(step) == 0:
                            # field list contains only strings
                            field_list.append(str(j))
                else:
                    if not star_or_int_re.search(t):
                        t = self.ALPHACONV[index][t.lower()]

                    try:
                        t = int(t)
                    except (ValueError, TypeError):
                        pass

                    if t in self.LOWMAP[index]:
                        t = self.LOWMAP[index][t]

                    if (t not in ['*', 'l'] and
                            (int(t) < self.RANGES[index][0] or
                             int(t) > self.RANGES[index][1])):
                        raise ValueError(f"[{expr_format}] is not acceptable, out of range")

                    res.append(t)

                    if index == self.DAY_OF_WEEK_FIELD_INDEX and nth:
                        if t not in nth_weekday_of_month:
                            nth_weekday_of_month[t] = set()
                        nth_weekday_of_month[t].add(nth)

            res = set(res)
            res = sorted(res, key=lambda i: f"{i:02}" if isinstance(i, int) else i)
            if len(res) == self.MAX_VALUE_PER_INDEX[index]:
                res = ['*']

            expanded.append(['*'] if (len(res) == 1
                                      and res[0] == '*')
                            else res)

        # Check to make sure the day of week combo in use is supported
        if nth_weekday_of_month:
            day_of_week_expanded_set = set(expanded[4])
            day_of_week_expanded_set = day_of_week_expanded_set.difference(
                                            nth_weekday_of_month.keys())
            day_of_week_expanded_set.discard("*")
            if day_of_week_expanded_set:
                raise ValueError(
                    "day-of-week field does not support mixing"
                    "literal values and nth day of week syntax."
                    f"Cron: '{expr_format}'    \
                        dow={day_of_week_expanded_set} vs nth={nth_weekday_of_month}")

        self.expanded = expanded
        self.nth_weekday_of_month = nth_weekday_of_month

    def get_next(self, ret_type=float):
        return self._get_next(ret_type, is_prev=False)

    def get_prev(self, ret_type=float):
        return self._get_next(ret_type, is_prev=True)

    def _get_next(self, ret_type=float, is_prev=False):
        expanded = self.expanded[:]
        nth_weekday_of_month = self.nth_weekday_of_month.copy()

        if ret_type not in (float, datetime):
            raise TypeError("Invalid ret_type, only 'float' or 'datetime' "
                            "is acceptable.")

        if expanded[2][0] != '*' and expanded[4][0] != '*':
            bak = expanded[4]
            expanded[4] = ['*']
            t1 = self._calc(self.cur, expanded, nth_weekday_of_month, is_prev)
            expanded[4] = bak
            expanded[2] = ['*']

            t2 = self._calc(self.cur, expanded, nth_weekday_of_month, is_prev)
            if not is_prev:
                result = t1 if t1 < t2 else t2
            else:
                result = t1 if t1 > t2 else t2
        else:
            result = self._calc(self.cur, expanded, nth_weekday_of_month, is_prev)
        self.cur = result

        if ret_type == datetime:
            result = datetime.fromtimestamp(result)
        return result

    def _calc(self, now, expanded, nth_weekday_of_month, is_prev):
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
                diff_month = nearest_diff_method(
                    d.month, expanded[3], self.MONTHS_IN_YEAR)
                days = DAYS[month - 1]
                if month == 2 and self.is_leap(year):
                    days += 1

                reset_day = days if is_prev else 1

                if diff_month is not None and diff_month != 0:
                    if is_prev:
                        d += relativedelta(months=diff_month)
                        reset_day = DAYS[d.month - 1]
                        d += relativedelta(
                            day=reset_day, hour=23, minute=59, second=59)
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
                if ('L' in expanded[2] or 'l' in expanded[2]) and days == d.day:
                    return False, d

                if is_prev:
                    days_in_prev_month = DAYS[
                        (month - 2) % self.MONTHS_IN_YEAR]
                    diff_day = nearest_diff_method(
                        d.day, expanded[2], days_in_prev_month)
                else:
                    diff_day = nearest_diff_method(d.day, expanded[2], days)

                if diff_day is not None and diff_day != 0:
                    if is_prev:
                        d += relativedelta(days=diff_day,
                                           hour=23, minute=59, second=59)
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
                        d += relativedelta(days=diff_day_of_week,
                                           hour=23, minute=59, second=59)
                    else:
                        d += relativedelta(days=diff_day_of_week,
                                           hour=0, minute=0, second=0)
                    return True, d
            return False, d

        def proc_day_of_week_nth(d):
            if '*' in nth_weekday_of_month:
                s = nth_weekday_of_month['*']
                for index in range(0, 7):
                    if index in nth_weekday_of_month:
                        nth_weekday_of_month[index].update(s)
                    else:
                        nth_weekday_of_month[index] = s
                del nth_weekday_of_month['*']

            candidates = []
            for wday, nth in nth_weekday_of_month.items():
                c = self._get_nth_weekday_of_month(d.year, d.month, wday)
                for n in nth:
                    if n == 'l':
                        candidate = c[-1]
                    elif len(c) < n:
                        continue
                    else:
                        candidate = c[n - 1]
                    if (
                        (is_prev and candidate <= d.day) or
                        (not is_prev and d.day <= candidate)
                    ):
                        candidates.append(candidate)

            if not candidates:
                if is_prev:
                    d += relativedelta(days=-d.day,
                                       hour=23, minute=59, second=59)
                else:
                    days = DAYS[month - 1]
                    if month == 2 and self.is_leap(year) is True:
                        days += 1
                    d += relativedelta(days=(days - d.day + 1),
                                       hour=0, minute=0, second=0)
                return True, d

            candidates.sort()
            diff_day = (candidates[-1] if is_prev else candidates[0]) - d.day
            if diff_day != 0:
                if is_prev:
                    d += relativedelta(days=diff_day,
                                       hour=23, minute=59, second=59)
                else:
                    d += relativedelta(days=diff_day,
                                       hour=0, minute=0, second=0)
                return True, d
            return False, d

        def proc_hour(d):
            if expanded[1][0] != '*':
                diff_hour = nearest_diff_method(d.hour, expanded[1], 24)
                if diff_hour is not None and diff_hour != 0:
                    if is_prev:
                        d += relativedelta(hours=diff_hour, minute=59, second=59)
                    else:
                        d += relativedelta(hours=diff_hour, minute=0, second=0)
                    return True, d
            return False, d

        def proc_minute(d):
            if expanded[0][0] != '*':
                diff_min = nearest_diff_method(d.minute, expanded[0], 60)
                if diff_min is not None and diff_min != 0:
                    if is_prev:
                        d += relativedelta(minutes=diff_min, second=59)
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
                     (proc_day_of_week_nth if self.nth_weekday_of_month
                      else proc_day_of_week),
                     proc_day_of_month,
                     proc_month]
        else:
            procs = [proc_month,
                     proc_day_of_month,
                     (proc_day_of_week_nth if self.nth_weekday_of_month
                      else proc_day_of_week),
                     proc_hour,
                     proc_minute,
                     proc_second]

        while abs(year - current_year) <= 1:
            next = False
            for proc in procs:
                (changed, dst) = proc(dst)
                if changed:
                    month, year = dst.month, dst.year
                    next = True
                    break
            if next:
                continue
            return mktime(dst.timetuple())

        raise RuntimeError("failed to find prev date")

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
        for _, d in enumerate(to_check):
            if d == 'l':
                # if 'L' then it is the last day of month
                # => its value of range_val
                d = range_val
            if d >= x:
                return d - x
        return to_check[0] - x + range_val

    def _get_prev_nearest_diff(self, x, to_check, range_val):
        candidates = to_check[:]
        candidates.reverse()
        for d in candidates:
            if d != 'l' and d <= x:
                return d - x
        if 'l' in candidates:
            return -x

        # candidate = candidates[0]

        # for c in candidates:
        #     # fixed: c < range_val
        #     # this code will reject all 31 day of month, 12 month, 59 second,
        #     # 23 hour and so on.
        #     # if candidates has just a element, this will not harmful.
        #     # but candidates have multiple elements, then values equal to
        #     # range_val will rejected.
        #     if c <= range_val:
        #         candidate = c
        #         break
        # if candidate > range_val:
        #     # fix crontab "0 6 30 3 *" candidates only a element,
        #     # then get_prev error return 2021-03-02 06:00:00
        #     return - x
        return candidates[0] - x - range_val

    def _get_nth_weekday_of_month(self, year, month, day_of_week):
        """ For a given year/month return a list of days in nth-day-of-month order.
        The last weekday of the month is always [-1].
        """
        w = (day_of_week + 6) % 7
        c = calendar.Calendar(w).monthdayscalendar(year, month)
        if c[0][0] == 0:
            c.pop(0)
        return tuple(i[0] for i in c)

    def is_leap(self, year):
        return year % 400 == 0 or (year % 4 == 0 and year % 100 != 0)


if __name__ == '__main__':

    base = datetime(2023, 2, 1)

    # next run
    cron = croniter('* * * * *', base)
    n1 = cron.get_next(datetime)
    print(n1)

    # first day of month
    cron = croniter('0 0 1 * *', base)
    n1 = cron.get_next(datetime)
    print(n1)

    # last day of month
    cron = croniter('0 0 L * *', base)
    n1 = cron.get_next(datetime)
    print(n1)

    # first Monday of month
    cron = croniter('0 0 * * 1#1', base)
    n1 = cron.get_next(datetime)
    print(n1)

    # last Monday of month
    cron = croniter('0 0 * * L1', base)
    n1 = cron.get_next(datetime)
    print(n1)

    # last Monday of February
    base = datetime(2023, 1, 1)
    cron = croniter('0 0 * feb L1', base)
    n1 = cron.get_next(datetime)
    print(n1)

    # leap year
    base = datetime(2024, 2, 1)
    cron = croniter('0 0 L * *', base)
    n1 = cron.get_next(datetime)
    print(n1)

    base = datetime(2024, 1, 1)
    for i in range(3):
        cron = croniter('0 0 L feb-mar *', base)
        base = cron.get_next(datetime)
        print(base)

    base = datetime(2024, 1, 1)
    for i in range(3):
        cron = croniter('0 0 L jan,dec *', base)
        base = cron.get_next(datetime)
        print(base)

    cron = croniter('0 0 2-L * *', base)
    base = cron.get_next(datetime)
    print(base)

    base = datetime(2023, 1, 1)
    for i in range(10):
        cron = croniter('0 0 * * mon-tue', base)
        base = cron.get_next(datetime)
        print(base)

    for i in range(10):
        cron = croniter('0 0 * * mon,fri', base)
        base = cron.get_next(datetime)
        print(base)
