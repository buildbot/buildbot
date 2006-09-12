
from buildbot.status.builder import SUCCESS, FAILURE, WARNINGS
from buildbot.steps.shell import ShellCommand

try:
    import cStringIO
    StringIO = cStringIO
except ImportError:
    import StringIO


class BuildEPYDoc(ShellCommand):
    name = "epydoc"
    command = ["make", "epydocs"]
    description = ["building", "epydocs"]
    descriptionDone = ["epydoc"]

    def createSummary(self, log):
        import_errors = 0
        warnings = 0
        errors = 0

        for line in StringIO(log.getText()):
            if line.startswith("Error importing "):
                import_errors += 1
            if line.find("Warning: ") != -1:
                warnings += 1
            if line.find("Error: ") != -1:
                errors += 1

        self.descriptionDone = self.descriptionDone[:]
        if import_errors:
            self.descriptionDone.append("ierr=%d" % import_errors)
        if warnings:
            self.descriptionDone.append("warn=%d" % warnings)
        if errors:
            self.descriptionDone.append("err=%d" % errors)

        self.import_errors = import_errors
        self.warnings = warnings
        self.errors = errors

    def evaluateCommand(self, cmd):
        if cmd.rc != 0:
            return FAILURE
        if self.warnings or self.errors:
            return WARNINGS
        return SUCCESS


class PyFlakes(ShellCommand):
    name = "pyflakes"
    command = ["make", "pyflakes"]
    description = ["running", "pyflakes"]
    descriptionDone = ["pyflakes"]
    flunkOnFailure = False

    def createSummary(self, log):
        unused_imports = 0
        undefined_names = 0
        redefinition_of_unused = 0
        star_import = 0
        misc = 0
        total = 0

        for line in StringIO(log.getText()).readlines():
            if "imported but unused" in line:
                unused_imports += 1
            elif "undefined name" in line:
                undefined_names += 1
            elif "redefinition of unused" in line:
                redefinition_of_unused += 1
            elif "*' used; unable to detect undefined names":
                star_import += 1
            else:
                misc += 1
            total += 1

        self.descriptionDone = self.descriptionDone[:]
        if unused_imports:
            self.descriptionDone.append("unused=%d" % unused_imports)
        if undefined_names:
            self.descriptionDone.append("undefined=%s" % undefined_names)
        if redefinition_of_unused:
            self.descriptionDone.append("redefs=%s" % redefinition_of_unused)
        if star_import:
            self.descriptionDone.append("import*=%s" % star_import)
        if misc:
            self.descriptionDone.append("misc=%s" % misc)
        self.num_warnings = total

        self.setProperty("pyflakes-unused", unused_imports)
        self.setProperty("pyflakes-undefined", undefined_names)
        self.setProperty("pyflakes-redefinitions", redefinition_of_unused)
        self.setProperty("pyflakes-import*", star_import)
        self.setProperty("pyflakes-misc", misc)
        self.setProperty("pyflakes-total", total)


    def evaluateCommand(self, cmd):
        if cmd.rc != 0:
            return FAILURE
        if self.num_warnings:
            return WARNINGS
        return SUCCESS

