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
            if "utf-16" in html:
                html = html.replace("utf-16", "utf-8")

            root = ElementTree.fromstring(html)
            root_dict = self.etree_to_dict(root)
            test_suites_dict = [self.etree_to_dict(r) for r in root.findall(".//test-suite/results/test-case/../..")]
            cxt['test_suites'] = test_suites_dict


            def testResult(test):
                if test['executed'].lower() == "true" and test['success'].lower() == "true":
                    return "passed"
                if test['executed'].lower() == "true" and ('result' in test and test['result'] is "Inconclusive"):
                    return "inconclusive"
                elif 'ignored' in test and  test['ignored'].lower() == "true":
                    return "ignored"
                elif test['executed'].lower() == "false":
                    return "skipped"
                else:
                    return "failed"

            #Collect summary information for each test suite
            time_count = 0
            total = 0
            for ts in test_suites_dict:
                for tso in ts['test-suite']:
                    tso['time'] = 0
                    tso['tests'] = 0
                    tso['passed'] = 0
                    tso['failed'] = 0
                    tso['ignored'] = 0
                    tso['inconclusive'] = 0
                    tso['skipped'] = 0
                    if 'results' in tso:
                        tso['tests'] = len(tso['results'])
                        for r in tso['results']:
                            total += 1
                            if r.has_key('time'):
                                t = float(r['time'])
                                time_count += t
                                tso['time'] += t
                                tso[testResult(r)] += 1
                            else:
                                tso['ignored'] += 1

            failed = int(root_dict['failures'])
            ignored = 0 if ('not_run' not in root_dict) else root_dict['not-run']
            skipped = 0 if ('skipped' not in root_dict) else root_dict['skipped']
            inconclusive = 0 if ('inconclusive' not in root_dict) else root_dict['inconclusive']
            success = (total - failed)
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