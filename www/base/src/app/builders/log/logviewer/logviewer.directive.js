/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
// logviewer. This directive uses jquery for simplicity
class Logviewer {
    constructor($log, $window, $timeout, $sce, $q, dataService, restService, ansicodesService) {
        $window = angular.element($window);

        const directive = function() {
            let self;
            let data = null;
            return self = {

            toggleAutoScroll() {
                if (self.scope.jumpToLine === "end") {
                    self.scope.jumpToLine = "none";
                    return self.scope.scroll_position = null;
                } else {
                    self.scope.jumpToLine = "end";
                    return self.scope.scroll_position = self.scope.log.num_lines;
                }
            },
            setHeight(elm) {
                const height = $window.height() - elm.offset().top;
                return elm.css({height: height + "px"});
            },

            updateLog() {
                var unwatch = self.scope.$watch("log", function(n, o) {
                    if (n != null) {
                        unwatch();
                        const { log } = self.scope;
                        self.scope.raw_url = `api/v2/logs/${log.logid}/raw`;
                        if (log.type === 'h') {
                            restService.get(`logs/${log.logid}/contents`).then(content => self.scope.content = $sce.trustAs($sce.HTML, content.logchunks[0].content));
                        }
                    }
                });
                return self.scope.$watch("log.num_lines", function(n, o) {
                    if (self.scope.jumpToLine === "end") {
                        self.scope.scroll_position = n;
                    } else if (self.scope.jumpToLine !== "none") {
                        self.scope.scroll_position = self.scope.jumpToLine;
                    }
                });
            },

            lines: {
                get(index, count) {
                    const { log } = self.scope;
                    if (index < 0) {
                        count += index;
                        index = 0;
                    }
                    if (count === 0) {
                        return $q.when([]);
                    }
                    if (self.requests == null) { self.requests = {}; }
                    const requestId = `${index}_${count}`;
                    if ((self.requests[requestId] == null)) {
                        self.requests[requestId] = $q(resolve =>
                            restService.get(`logs/${log.logid}/contents`, {offset:index, limit:count}).then(function(content) {
                                content = content.logchunks;
                                const ret = [];
                                if (content.length === 0) {
                                    resolve(ret);
                                    return;
                                }
                                let offset = index;
                                const lines = content[0].content.split("\n");
                                // there is a trailing '\n' generates an empty line in the end
                                if (lines.length > 1) {
                                    lines.pop();
                                }
                                for (let line of Array.from(lines)) {
                                    let logclass = "o";
                                    if ((line.length > 0) && (self.scope.log.type === 's')) {
                                        logclass = line[0];
                                        line = line.slice(1);
                                    }
                                    ret.push({
                                        content: ansicodesService.ansi2html(line),
                                        class: `log_${logclass}`
                                    });
                                    offset += 1;
                                }
                                resolve(ret);
                            })
                        );
                    }
                    return self.requests[requestId];
                }
            },

            // controller is called first and need to setup the scope for ui-scroll to find lines
            controller($scope) {
                $scope.lines = self.lines;
                self.scope = $scope;
                data = dataService.open().closeOnDestroy($scope);
                return self.updateLog();
            },

            link(scope, elm, attr) {
                elm = elm.children("pre");
                self.setHeight(elm);
                self.elm = elm;
                self.raw = elm[0];
                $window.resize(() => self.setHeight(elm));
            }
        };
        };

        return {
            replace: true,
            transclude: true,
            restrict: 'E',
            scope: {log:"=", jumpToLine:"="},
            template: require('./logviewer.tpl.jade'),
            controller: ["$scope", function($scope) {
                const self = directive();
                $scope.logviewer = self;
                return self.controller($scope);
            }
            ],
            link(scope, elm, attr) {
                ansicodesService.injectStyle();
                scope.logviewer.link(scope, elm, attr);
            }
        };
    }
}


angular.module('app')
.directive('logviewer', ['$log', '$window', '$timeout', '$sce', '$q', 'dataService', 'restService', 'ansicodesService', Logviewer]);
