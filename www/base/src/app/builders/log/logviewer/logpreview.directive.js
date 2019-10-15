/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Logpreview {
    constructor($sce, restService, ansicodesService, bbSettingsService) {
        return {
            replace: true,
            transclude: true,
            restrict: 'E',
            scope: {
                log: "<",
                fulldisplay: "<",
                buildnumber: "<",
                builderid: "<",
                step: "<"
            },
            template: require('./logpreview.tpl.jade'),
            controllerAs: "logpreview",
            bindToController: true,
            controller: ["$scope", function ($scope) {
                this.$onInit = function () {
                    let loadLines;
                    this.settings = bbSettingsService.getSettingsGroup("LogPreview");
                    let pendingRequest = null;
                    $scope.$on('$destroy', function () {
                        if (pendingRequest) {
                            pendingRequest.cancel();
                        }
                    });
                    const loading = $sce.trustAs($sce.HTML, "...");

                    let unwatchLog = null;
                    let unwatchLines = null;
                    $scope.$watch("logpreview.fulldisplay", (n, o) => {
                        // Cancel previous requests and stop fetching new lines first
                        if (pendingRequest) {
                            pendingRequest.cancel();
                        }
                        if (unwatchLines) {
                            unwatchLines();
                        }
                        // Start fetching lines when the preview is visible.
                        if (n) {
                            unwatchLog = $scope.$watch("logpreview.log", fetchLog);
                        }
                    });

                    var fetchLog = (n, o) => {
                        this.log.lines = [];
                        if ((n == null)) {
                            return;
                        }
                        unwatchLog();
                        if (unwatchLines) {
                            unwatchLines();
                        }
                        if (this.log.type === 'h') {
                            pendingRequest = restService.get(`logs/${this.log.logid}/contents`);
                            pendingRequest.then(content => {
                                this.log.content = $sce.trustAs($sce.HTML, content.logchunks[0].content);
                            });
                        } else {
                            unwatchLines = $scope.$watch("logpreview.log.num_lines", loadLines);
                        }
                    };

                    loadLines = num_lines => {
                        let limit, offset;
                        if (this.log.lines.length === 0) {
                            // initial load. only load the last few lines
                            offset = this.log.num_lines - this.settings.loadlines.value;
                            limit = this.settings.loadlines.value;
                            if (offset < 0) {
                                offset = 0;
                                limit = this.log.num_lines;
                            }
                        } else {
                            // The last element of the line is the last line loaded
                            // This might be actually a loading marker
                            offset = this.log.lines[this.log.lines.length - 1].number + 1;
                            limit = this.log.num_lines - offset;
                            // if log is advancing very fast no need to load too much lines
                            if (limit > this.settings.maxlines.value) {
                                offset = this.log.num_lines - this.settings.maxlines.value;
                                limit = this.settings.maxlines.value;
                            }
                        }

                        if (limit === 0) {
                            return;
                        }

                        // this acts as a marker of the last loaded element
                        // note that several elements can be loading at the same time
                        // as we follow the log updates

                        const loading_element = {
                            content: loading,
                            number: (offset + limit) - 1
                        };
                        this.log.lines.push(loading_element);

                        pendingRequest = restService.get(`logs/${this.log.logid}/contents`, {
                            offset,
                            limit
                        });
                        pendingRequest.then(content => {
                            ({
                                content
                            } = content.logchunks[0]);
                            const lines = content.split("\n");
                            // there is a trailing '\n' generates an empty line in the end
                            if (lines.length > 1) {
                                lines.pop();
                            }
                            let number = offset;
                            // remove the loading element
                            this.log.lines.splice(this.log.lines.indexOf(loading_element), 1);
                            for (let line of Array.from(lines)) {
                                let logclass = "o";
                                if ((line.length > 0) && (this.log.type === 's')) {
                                    logclass = line[0];
                                    line = line.slice(1);
                                }
                                // we just push the lines in the end, and will apply sort eventually
                                this.log.lines.push({
                                    content: $sce.trustAs($sce.HTML, ansicodesService.ansi2html(line)),
                                    class: `log_${logclass}`,
                                    number
                                });
                                number += 1;
                            }
                            this.log.lines.sort((a, b) => a.number - b.number);
                            this.log.lines.splice(0, this.log.lines.length - this.settings.maxlines.value);
                        });
                    };
                }
            }],
            link(scope, elm, attr) {
                ansicodesService.injectStyle();
            }
        };
    }
}


angular.module('app')
    .directive('logpreview', ['$sce', 'restService', 'ansicodesService', 'bbSettingsService', Logpreview]);
