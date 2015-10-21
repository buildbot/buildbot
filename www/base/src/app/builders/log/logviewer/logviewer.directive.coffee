# logviewer. This directive uses jquery for simplicity
class Logviewer extends Directive
    constructor: ($log, $window, buildbotService, $timeout, $sce, $q) ->
        $window = angular.element($window)

        directive = ->
            self =
            num_lines: 0
            auto_scroll: true

            setHeight: (elm) ->
                height = $window.height() - elm.offset().top
                elm.css({height: height + "px"})

            lines:
                get: (index, count) ->
                    self.log_p.then (log) ->
                        if index < 0
                            count += index
                            index = 0
                        return log.all('contents').getList(offset:index, limit:count).then (content) ->
                            ret = []
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
                            ret
            updateLog: ->
                unwatch = self.scope.$watch "logid", (n, o) ->
                    if n?
                        self.logid = n
                        unwatch()
                        self.log_d.resolve(buildbotService.one('logs', self.logid))
                self.log_p.then (log) ->
                    log.bind(self.scope)
                    .then (log) ->
                        self.scope.raw_url = "/api/v2/logs/#{log.id}/raw"
                        if log.type == 'h'
                            log.all('contents').getList().then (content) ->
                                self.scope.content = $sce.trustAs($sce.HTML, content[0].content)

            # controller is called first and need to setup the scope for ui-scroll to find lines
            controller: ($scope) ->
                $scope.lines = self.lines
                self.log_d = $q.defer()
                self.log_p = self.log_d.promise
                self.scope = $scope
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
            scope: {logid:"="}
            templateUrl: "views/logviewer.html"
            controller: ["$scope", ($scope) ->
                self = directive()
                $scope.logviewer = self
                self.controller($scope)
            ]
            link: (scope, elm, attr) ->
                scope.logviewer.link(scope, elm, attr)
        }
