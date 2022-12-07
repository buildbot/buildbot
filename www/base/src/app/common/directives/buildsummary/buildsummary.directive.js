/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS104: Avoid inline assignments
 * DS204: Change includes calls to have a more natural evaluation order
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */

import moment from 'moment';
import {
    memoize
} from 'lodash'

class Buildsummary {
    constructor(RecursionHelper) {
        return {
            replace: true,
            restrict: 'E',
            scope: {
                buildid: '=?',
                build: '=?',
                condensed: '=?',
                parentbuild: '=?',
                parentrelationship: '=?'
            },
            bindToController: true,
            template: function (element, attrs) {
                          if (attrs.type === "tooltip")
                              return require('./buildsummarytooltip.tpl.jade');
                          else
                              return require('./buildsummary.tpl.jade');
                      },
            compile: RecursionHelper.compile,
            controller: '_buildsummaryController',
            controllerAs: 'buildsummary'
        };
    }
}

class _buildsummary {
    constructor($scope, dataService, resultsService, buildersService, $urlMatcherFactory, $location, $interval, RESULTS, bbSettingsService, config) {
        const self = this;
        // make resultsService utilities available in the template
        _.mixin($scope, resultsService);

        const buildrequestURLMatchers = []
        const buildURLMatchers = []
        const baseUrls = config['buildbotURLs'] || [config['buildbotURL']]
        for (const baseurl of baseUrls) {
            buildrequestURLMatchers.push($urlMatcherFactory.compile(
                `${baseurl}#/buildrequests/{buildrequestid:[0-9]+}`))
            buildURLMatchers.push($urlMatcherFactory.compile(
                `${baseurl}#/builders/{builderid:[0-9]+}/builds/{buildnumber:[0-9]+}`));
        }

        function execMatchers(matchers, url) {
            for (const matcher of matchers) {
                const res = matcher.exec(url)
                if (res) {
                    return res
                }
            }
            return null
        }
        this.stepUpdated = function(step) {
            step.fulldisplay = (step.complete === false) || (step.results > 0);
            if (step.complete) {
                step.duration = step.complete_at - step.started_at;
            }
            step.other_urls = []
            step.buildrequests = []
            step.builds = []
            if (step.buildrequestsCurrentPage === undefined) {
                // uib-pagination starts counting at 1...
                step.buildrequestsCurrentPage = 1
            }
            for (let url of step.urls) {
                let brRes = execMatchers(buildrequestURLMatchers, url.url)
                if (brRes !== null) {
                    step.buildrequests.push({
                        buildrequestid: brRes.buildrequestid
                    })
                    continue
                }
                let buildRes = execMatchers(buildURLMatchers, url.url)
                if (buildRes !== null) {
                    step.builds.push({
                        builderid: buildRes.builderid,
                        buildnumber: buildRes.buildnumber
                    })
                    continue
                }
                step.other_urls.push(url)
            }
        }
        this.$onInit = function () {

            // to get an update of the current builds every seconds, we need to update self.now
            // but we want to stop counting when the scope destroys!
            const stop = $interval(() => {
                this.now = moment().unix();
            }, 1000);
            $scope.$on("$destroy", () => $interval.cancel(stop));
            $scope.settings = bbSettingsService.getSettingsGroup("LogPreview");
            $scope.trigger_step_page_size = bbSettingsService.getSettingsGroup("Build").trigger_step_page_size.value;
            $scope.show_urls = bbSettingsService.getSettingsGroup("Build").show_urls.value;

            const NONE = 0;
            const ONLY_NOT_SUCCESS = 1;
            const EVERYTHING = 2;
            let details = EVERYTHING;
            if (this.condensed) {
                details = NONE;
            }
            this.toggleDetails = () => details = (details + 1) % 3;

            this.levelOfDetails = function () {
                switch (details) {
                    case NONE:
                        return "None";
                    case ONLY_NOT_SUCCESS:
                        return "Problems";
                    case EVERYTHING:
                        return "All";
                }
            };

            this.isStepDisplayed = function (step) {
                if (details === EVERYTHING) {
                    return !step.hidden;
                } else if (details === ONLY_NOT_SUCCESS) {
                    return (step.results == null) || (step.results !== RESULTS.SUCCESS);
                } else if (details === NONE) {
                    return false;
                }
            };

            this.assignDisplayedStepNumber = function (step) {
                if (step.number === 0)
                    this.display_count = 0
                if (this.isStepDisplayed(step))
                    step.display_num = (this.display_count)++;
                return true;
            };

            this.getDisplayedStepCount = function () {
                return self.steps.filter(this.isStepDisplayed).length;
            };

            this.getBuildProperty = function (property) {
                const hasProperty = self.properties && self.properties.hasOwnProperty(property);
                if (hasProperty) {
                    return self.properties[property][0];
                } else {
                    return null;
                }
            };

            this.isSummaryLog = log => log.name.toLowerCase() === "summary";

            this.expandByName = function (log) {
                let needle;
                return (log.num_lines > 0) && (needle = log.name.toLowerCase(), Array.from($scope.settings.expand_logs.value.toLowerCase().split(";")).includes(needle));
            };

            // Returns the logs, sorted with the "Summary" log first, if it exists in the step's list of logs
            this.getLogs = function (step) {
                const summaryLogs = step.logs.filter(log => this.isSummaryLog(log));
                const logs = summaryLogs.concat(step.logs.filter(log => !this.isSummaryLog(log)));
                return logs;
            };


            this.toggleFullDisplay = function () {
                this.fulldisplay = !this.fulldisplay;
                if (this.fullDisplay) {
                    details = EVERYTHING;
                }
                return Array.from(this.steps).map((step) =>
                    (step.fulldisplay = this.fulldisplay));
            };

            this.closeParentModal = function () {
                if ('modal' in $scope.$parent)
                    return $scope.$parent.modal.close();
            };

            const data = dataService.open().closeOnDestroy($scope);
            $scope.$watch((() => this.buildid), function (buildid) {
                if ((buildid == null)) {
                    return;
                }
                data.getBuilds(buildid).onNew = build => self.build = build;
            });

            $scope.$watch((() => this.build), function (build) {
                if ((build == null)) {
                    return;
                }
                if (self.builder) {
                    return;
                }
                self.builder = buildersService.getBuilder(build.builderid);

                build.getProperties().onNew = function (properties) {
                    self.properties = properties;
                    self.reason = self.getBuildProperty('reason');
                };

                $scope.$watch((() => details), function (details) {
                    if ((details !== NONE) && (self.steps == null)) {
                        self.steps = build.getSteps();

                        self.steps.onNew = function (step) {
                            step.logs = step.getLogs();
                            // onUpdate is only called onUpdate, not onNew
                            // but we need to update our additional needed attributes
                            self.steps.onUpdate(step);
                        };
                        self.steps.onUpdate = self.stepUpdated
                    }
                });
            });
            $scope.$watch((() => this.parentbuild), function (build, o) {
                if ((build == null)) {
                    return;
                }
                self.parentbuilder = buildersService.getBuilder(build.builderid);
            });
        }
    }
}


angular.module('common')
    .directive('buildsummary', ['RecursionHelper', Buildsummary])
    .controller('_buildsummaryController', ['$scope', 'dataService', 'resultsService', 'buildersService', '$urlMatcherFactory', '$location', '$interval', 'RESULTS', 'bbSettingsService', 'config', _buildsummary]);
