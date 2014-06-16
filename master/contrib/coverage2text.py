#!/usr/bin/env python

import sys

from coverage import coverage
from coverage.results import Numbers
from coverage.summary import SummaryReporter
from twisted.python import usage

# this is an adaptation of the code behind "coverage report", modified to
# display+sortby "lines uncovered", which (IMHO) is more important of a
# metric than lines covered or percentage covered. Concentrating on the files
# with the most uncovered lines encourages getting the tree and test suite
# into a state that provides full line-coverage on all files.

# much of this code was adapted from coverage/summary.py in the 'coverage'
# distribution, and is used under their BSD license.


class Options(usage.Options):
    optParameters = [
        ("sortby", "s", "uncovered", "how to sort: uncovered, covered, name"),
    ]


class MyReporter(SummaryReporter):

    def report(self, outfile=None, sortby="uncovered"):
        self.find_code_units(None, ["/System", "/Library", "/usr/lib",
                                    "buildbot/test", "simplejson"])

        # Prepare the formatting strings
        max_name = max([len(cu.name) for cu in self.code_units] + [5])
        fmt_name = "%%- %ds  " % max_name
        fmt_err = "%s   %s: %s\n"
        header1 = (fmt_name % "") + "     Statements    "
        header2 = (fmt_name % "Name") + " Uncovered  Covered"
        fmt_coverage = fmt_name + "%9d  %7d "
        if self.branches:
            header1 += "   Branches   "
            header2 += " Found  Excutd"
            fmt_coverage += " %6d %6d"
        header1 += "  Percent"
        header2 += "  Covered"
        fmt_coverage += " %7d%%"
        if self.show_missing:
            header1 += "          "
            header2 += "   Missing"
            fmt_coverage += "   %s"
        rule = "-" * len(header1) + "\n"
        header1 += "\n"
        header2 += "\n"
        fmt_coverage += "\n"

        if not outfile:
            outfile = sys.stdout

        # Write the header
        outfile.write(header1)
        outfile.write(header2)
        outfile.write(rule)

        total = Numbers()
        total_uncovered = 0

        lines = []
        for cu in self.code_units:
            try:
                analysis = self.coverage._analyze(cu)
                nums = analysis.numbers
                uncovered = nums.n_statements - nums.n_executed
                total_uncovered += uncovered
                args = (cu.name, uncovered, nums.n_executed)
                if self.branches:
                    args += (nums.n_branches, nums.n_executed_branches)
                args += (nums.pc_covered,)
                if self.show_missing:
                    args += (analysis.missing_formatted(),)
                if sortby == "covered":
                    sortkey = nums.pc_covered
                elif sortby == "uncovered":
                    sortkey = uncovered
                else:
                    sortkey = cu.name
                lines.append((sortkey, fmt_coverage % args))
                total += nums
            except KeyboardInterrupt:                       # pragma: no cover
                raise
            except:
                if not self.ignore_errors:
                    typ, msg = sys.exc_info()[:2]
                    outfile.write(fmt_err % (cu.name, typ.__name__, msg))
        lines.sort()
        if sortby in ("uncovered", "covered"):
            lines.reverse()
        for sortkey, line in lines:
            outfile.write(line)

        if total.n_files > 1:
            outfile.write(rule)
            args = ("TOTAL", total_uncovered, total.n_executed)
            if self.branches:
                args += (total.n_branches, total.n_executed_branches)
            args += (total.pc_covered,)
            if self.show_missing:
                args += ("",)
            outfile.write(fmt_coverage % args)


def report(o):
    c = coverage()
    c.load()
    r = MyReporter(c, show_missing=False, ignore_errors=False)
    r.report(sortby=o['sortby'])

if __name__ == '__main__':
    o = Options()
    o.parseOptions()
    report(o)
