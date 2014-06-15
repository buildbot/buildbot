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
from xml.etree import ElementTree
from buildbot.status.web.base import HtmlResource, path_to_builder, path_to_builders, path_to_codebases, path_to_build


class XMLTestResource(HtmlResource):
    def __init__(self, log, step_status):
        HtmlResource.__init__(self)
        self.log = log
        self.step_status = step_status

    def etree_to_dict(self, t):
        d = {t.tag: map(self.etree_to_dict, list(t))}
        d.update((k, v) for k, v in t.attrib.iteritems())
        d['text'] = t.text
        return d

    def test_result_to_status(self, test, nose_test):
        if not nose_test:
            if test['executed'].lower() == "true" and ('success' in test and test['success'].lower() == "true"):
                return ("passed", "Pass")
            if test['executed'].lower() == "true" and ('result' in test and test['result'].lower() == "inconclusive"):
                return "inconclusive", "Inconclusive"
            elif 'ignored' in test and test['ignored'].lower() == "true":
                return "ignored", "Ignored"
            elif test['executed'].lower() == "false":
                return "skipped", "Skipped"
            else:
                return "failed", "Failure"
        else:
            if test.has_key("testcase") and len(test["testcase"]) > 0 and test["testcase"][0].has_key("error"):
                return "failed", "Failure"
            return "passed", "Pass"

    def test_result_xml_to_dict(self, test, nose_test):
        result = {'result': self.test_result_to_status(test, nose_test)[1]}

        if test.has_key('time'):
            result['time'] = float(test['time'])
        if test.has_key('name'):
            result['name'] = test['name']
        if test.has_key('success'):
            result['success'] = test['success']

        failure_text = []
        if test.has_key("test-case"):
            for ft in test['test-case']:
                if ft.has_key('reason'):
                    failure_text = ft['reason']
                if ft.has_key('failure'):
                    failure_text = ft['failure']

        if nose_test:
            if test.has_key("testcase") and len(test["testcase"]) > 0 and test["testcase"][0].has_key("error"):
                result["success"] = "false"
                failure_text = [{"text": test["testcase"][0]["message"]}]
            else:
                result["success"] = "true"

        result['failure_text'] = failure_text

        return result

    def test_dict(self):
        return {'time': 0,
                'tests': 0,
                'passed': 0,
                'failed': 0,
                'ignored': 0,
                'inconclusive': 0,
                'skipped': 0,
                'results': [],
                'name': "???"}


    def content(self, req, cxt):
        s = self.step_status
        b = s.getBuild()
        builder_status = b.getBuilder()
        project = builder_status.getProject()
        cxt['builder_name'] = b.getBuilder().getFriendlyName()
        cxt['path_to_builder'] = path_to_builder(req, builder_status)
        cxt['path_to_builders'] = path_to_builders(req, project)
        cxt['path_to_codebases'] = path_to_codebases(req, project)
        cxt['path_to_build'] = path_to_build(req, b)
        cxt['build_number'] = b.getNumber()
        cxt['selectedproject'] = project

        try:
            html = self.log.html
            nose_test = False
            if "nosetests" in html:
                nose_test = True
            if "utf-16" in html:
                html = html.replace("utf-16", "utf-8")

            root = ElementTree.fromstring(html)
            root_dict = self.etree_to_dict(root)
            xpath =".//test-suite/results/test-case/../.."
            if nose_test:
                xpath = ".//testcase"
            test_suites_dict = [self.etree_to_dict(r) for r in root.findall(xpath)]

            def parseTest(test, nose_test):
                total = 0
                time_count = 0
                test_parent = self.test_dict()

                def updateTime(result_object):
                    t = 0
                    if result_object.has_key('time'):
                        t = result_object['time']
                        test_parent['time'] += t

                    return t

                if test.has_key("name"):
                    test_parent["name"] = test["name"]

                if not nose_test and 'results' in test:
                    test_parent['tests_length'] = len(test['results'])
                    for r in tso['results']:
                        result_object = self.test_result_xml_to_dict(r, nose_test)
                        test_parent['results'].append(result_object)
                        total += 1

                        time_count += updateTime(result_object)
                        test_parent[self.test_result_to_status(r, nose_test)[0]] += 1
                elif nose_test:
                    result_object = self.test_result_xml_to_dict(test, nose_test)
                    test_parent['results'].append(result_object)

                    total += 1
                    time_count += updateTime(result_object)
                    test_parent[self.test_result_to_status(test, nose_test)[0]] += 1

                return test_parent, total, time_count


            # Collect summary information for each test suite
            time_count = 0
            total = 0
            output_tests = []

            if not nose_test:
                for ts in test_suites_dict:
                    tests = ts['test-suite'] if not nose_test else ts
                    for tso in tests:
                        o, c, t = parseTest(tso, nose_test)
                        o["name"] = ts["name"]
                        output_tests.append(o)
                        total += c
                        time_count += t
            elif nose_test:
                classes = {}
                for tso in test_suites_dict:
                    class_name = tso["classname"]
                    o, c, t = parseTest(tso, nose_test)
                    if class_name not in classes:
                        classes[class_name] = self.test_dict()
                        classes[class_name]["name"] = class_name

                    classes[class_name]["results"].append(o["results"][0])
                    classes[class_name]["passed"] += o["passed"]
                    classes[class_name]["failed"] += o["failed"]
                    classes[class_name]["time"] += t
                    classes[class_name]["tests"] += c
                    total += c
                    time_count += t

                output_tests = classes.values()


            cxt['test_suites'] = output_tests

            failed = int(root_dict['failures'])
            ignored = int(0 if ('not_run' not in root_dict) else root_dict['not-run'])
            skipped = int(0 if ('skipped' not in root_dict) else root_dict['skipped'])
            inconclusive = int(0 if ('inconclusive' not in root_dict) else root_dict['inconclusive'])
            success = (total - failed - inconclusive - skipped - ignored)

            success_per = 0
            if success != 0 and total != 0:
                success_per = (float(success) / float(total)) * 100.0

            cxt['summary'] = {
                'total': total,
                'success': success,
                'success_rate': success_per,
                'failed': failed,
                'ignored': ignored,
                'skipped': skipped,
                'inconclusive': inconclusive,
                'time': time_count
            }
        except ElementTree.ParseError as e:
            print "Error with parsing XML: {0}".format(e)

        template = req.site.buildbot_service.templates.get_template("xmltestresults.html")
        return template.render(**cxt)