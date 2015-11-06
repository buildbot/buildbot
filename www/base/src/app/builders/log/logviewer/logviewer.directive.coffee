# logviewer. This directive uses jquery for simplicity
class Logviewer extends Directive
    constructor: ($log, $window, $timeout, $sce, $q, dataService, restService) ->
        $window = angular.element($window)

        directive = ->
            data = null
            self =
            num_lines: 0
            auto_scroll: true

            setHeight: (elm) ->
                height = $window.height() - elm.offset().top
                elm.css({height: height + "px"})

            updateLog: ->
                unwatch = self.scope.$watch "log", (n, o) ->
                    if n?
                        unwatch()
                        log = self.scope.log
                        self.scope.raw_url = "/api/v2/logs/#{log.logid}/raw"
                        if log.type == 'h'
                            restService.get("logs/#{log.logid}/contents").then (content) ->
                                self.scope.content = $sce.trustAs($sce.HTML, content.logchunks[0].content)

            lines:
                get: (index, count) ->
                    log = self.scope.log
                    if index < 0
                        count += index
                        index = 0
                    self.requests ?= {}
                    requestId = "#{index}_#{count}"
                    if not self.requests[requestId]?
                        self.requests[requestId] = $q (resolve) ->
                            restService.get("logs/#{log.logid}/contents", offset:index, limit:count).then (content) ->
                                content = content.logchunks
                            # log.getContents(offset:index, limit:count).then (content) ->
                                ret = []
                                if content.length == 0
                                    resolve(ret)
                                    return
                                offset = index
                                lines = content[0].content.split("\n")
                                # there is a trailing '\n' generates an empty line in the end
                                if lines.length > 1
                                    lines.pop()
                                for line in lines
                                    logclass = "o"
                                    if line.length > 0 and (self.scope.log.type == 's')
                                        logclass = line[0]
                                        line = line[1..]
                                    ret.push
                                        content: line
                                        class: "log_" + logclass
                                    offset += 1
                                resolve(ret)
                    return self.requests[requestId]

            # controller is called first and need to setup the scope for ui-scroll to find lines
            controller: ($scope) ->
                $scope.lines = self.lines
                self.scope = $scope
                data = dataService.open($scope)
                self.updateLog()

            link: (scope, elm, attr) ->
                elm = elm.children("pre")
                self.setHeight(elm)
                self.elm = elm
                self.raw = elm[0]
                $window.resize(-> self.setHeight(elm))

                return null

        return {
            replace: true
            transclude: true
            restrict: 'E'
            scope: {log:"="}
            templateUrl: "views/logviewer.html"
            controller: ["$scope", ($scope) ->
                self = directive()
                $scope.logviewer = self
                self.controller($scope)
            ]
            link: (scope, elm, attr) ->
                scope.logviewer.link(scope, elm, attr)
        }
