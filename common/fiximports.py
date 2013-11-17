#!/usr/bin/env python
'''Check and sort import statement from a python file '''

import re
import sys


class FixImports(object):

    '''
    I can be used to check and sort import statement of a python file
    Please use sortImportGroups() method
    '''

    _regexImport = re.compile(r"^import\s+(.*)")
    _regexFromImport = re.compile(r"^from\s+([a-zA-Z0-9\._]+)\s+import\s+(.*)$")
    _regexFromFutureImport = re.compile(r"^from\s+__future__\s+import\s+(.*)$")

    def printErrorMsg(self, filename, lineNb, errorMessage):
        ''' I print the error message following pylint convention'''
        print ("%(filename)s:%(line_nb)s: %(error_msg)s" %
               dict(filename=filename,
                    line_nb=lineNb,
                    error_msg=errorMessage))

    def isImportLine(self, line):
        '''I return True is the given line is an import statement, False otherwize'''
        return self._regexImport.match(line) or self._regexFromImport.match(line)

    def isBadLineFixable(self, line):
        '''I return True is the given line is an import line than I know how to split'''
        if self.isImportLine(line) and '(' not in line:
            return True
        return False

    def analyzeLine(self, filename, line, lineNb):
        '''I look at the line and print all error I find'''
        res = True
        if self.isImportLine(line):
            if ',' in line:
                self.printErrorMsg(filename, lineNb,
                                   "multiple modules imported on one line - will fix")
                res = False
            if '\\' in line:
                self.printErrorMsg(filename, lineNb,
                                   "line-continuation character found - will fix.")
                res = False
            # these two don't occur in the Buildbot codebase, so we don't try to
            # fix them
            if ';' in line:
                self.printErrorMsg(filename, lineNb,
                                   "multiple import statement on one line. "
                                   "Put each import on its own line.")
                res = False
            if '(' in line:
                self.printErrorMsg(filename, lineNb,
                                   "parenthesis character found. "
                                   "Please import each module on a single line")
                res = False
        return res

    def importOrder(self, line):
        '''
        I define how import lines should be sorted
        return a tuple of order criterias sorted be importance
        '''
        ret = ("__future__" not in line,  # always put __future__ import first
               self._regexFromImport.match(line) is not None,  # import before from import
               line,  # then lexicographic order
               )
        return ret

    def sortImportGroups(self, filename, data=None):
        '''
        I perform the analysis of the given file, print the error I find and try to split and
        sort the import statement
        '''
        lines = data.split("\n")
        res = True
        for cur_line_nb, line in enumerate(lines):
            if not self.analyzeLine(filename, line, cur_line_nb):
                if not self.isBadLineFixable(line):
                    res = False
        if not res:
            return False, data

        # First split the import we can split
        newlines = []
        self.groups = []
        self.group_start = None

        def maybeEndGroup():
            if self.group_start is not None:
                self.groups.append((self.group_start, len(newlines)))
                self.group_start = None

        iter = lines.__iter__()
        while True:
            try:
                line = iter.next()
            except StopIteration:
                break
            if self.isImportLine(line):
                # join any continuation lines (\\)
                while line[-1] == '\\':
                    line = line[:-1] + iter.next()
                if self.group_start is None:
                    self.group_start = len(newlines)

                if self.isBadLineFixable(line):
                    match = self._regexFromImport.match(line)
                    if match:
                        module = match.group(1)
                        imports = [s.strip() for s in match.group(2).split(",")]
                        for imp in imports:
                            newlines.append("from %s import %s" % (module, imp))
                        continue
            else:
                maybeEndGroup()
            newlines.append(line)

        maybeEndGroup()

        lines = newlines
        for start, end in self.groups:
            lines[start:end] = sorted(lines[start:end], key=self.importOrder)

        # reiterate line by line to split mixed groups
        splitted_groups_lines = []
        prev_import_line_type = ""
        for line in lines:
            if not line.strip() or not self.isImportLine(line):
                splitted_groups_lines.append(line)
                prev_import_line_type = ""
            else:
                import_match = self._regexImport.match(line)
                from_match = self._regexFromImport.match(line)
                current_line_type = None
                if import_match is not None:
                    module = import_match
                    current_line_type = "import"
                elif from_match is not None:
                    module = from_match
                    current_line_type = "from"
                assert(current_line_type)
                if prev_import_line_type and current_line_type != prev_import_line_type:
                    splitted_groups_lines.append("")
                prev_import_line_type = current_line_type
                splitted_groups_lines.append(line)

        return True, "\n".join(splitted_groups_lines)


def main():
    '''I am the main method'''
    if len(sys.argv) != 2:
        print "usage: %s <python file>" % (sys.argv[0])
        sys.exit(1)

    filename = sys.argv[1]

    with open(filename, 'r') as filedesc:
        data = filedesc.read()
    res, content = FixImports().sortImportGroups(filename, data)
    if not res:
        sys.exit(1)

    with open(filename, 'w') as filedesc:
        filedesc.write(content)
    if data != content:
        print "import successfully reordered for file: %s" % (filename)
    sys.exit(0)

if __name__ == "__main__":
    main()
