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
from buildbot.util.yaml_config import YamlConfig
import os

class TestYamlConfig(unittest.TestCase):
    def openYaml(self, fn):
        specfn=None
        fn = os.path.join(os.path.dirname(__file__), "inputs","yaml_config",
                          fn+".yaml")
        if fn.find("fail")>=0:
            specfn = fn[:fn.index(".fail")]+".meta.yaml"
        typefn = None
        if fn.find("complex")>=0:
            typefn = os.path.join(os.path.dirname(__file__), "inputs","yaml_config","types.meta.yaml")
        return YamlConfig(fn,specfn=specfn,additionnal_types=typefn)
    def failTest(self,fn, failtest):
        failed = False
        try:
            self.openYaml(fn)
        except Exception,e:
            import traceback
            if not failtest in str(e):
                traceback.print_exc()
            self.failUnlessIn(failtest,str(e))
            failed = True
        self.failUnless(failed)

    def test_basic(self):
        y = self.openYaml("basic")
        self.failIf(y.field1 != "OK")
    def test_basic_invalidKey(self):
        self.failTest("basic.fail1", "but only those keys are accepted")
    def test_basic_inValues(self):
        self.failTest("basic.fail2", "should be one of")

    def test_complex(self):
        self.openYaml("complex")

    def test_complexDefault(self):
        y = self.openYaml("complex")
        self.failUnlessEqual(y.slaves[0].caps.speed, "fast")

    def test_complex_badlocation(self):
        self.failTest("complex.fail1", "should be one of")

    def test_complex_duplicateInSet(self):
        self.failTest("complex.fail2", "is included several times in a set")

    def test_complex_missingRequired(self):
        self.failTest("complex.fail3", "needs to define the option location")

    def test_complex_missingRequired2(self):
        self.failTest("complex.fail4", "needs to define the option builder")

    def test_funny(self):
        self.openYaml("funny_complex")

    def test_funnyDuplicate(self):
        self.failTest("funny_complex.fail1", "is included several times in a set")

    def test_conditionnal_required(self):
        self.openYaml("conditionnal_required")

    def test_conditionnal_required_absent(self):
        self.failTest("conditionnal_required.fail1", "needs to define the option field1")

    def test_conditionnal_notrequired(self):
        self.openYaml("conditionnal_required.fail2")

    def test_conditionnal_forbidden(self):
        self.failTest("conditionnal_required.fail3", "option field1 is forbidden")

