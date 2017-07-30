class Logpreview extends Directive
    constructor: ($sce, restService, ansicodesService, bbSettingsService) ->
        return {
            replace: true
            transclude: true
            restrict: 'E'
            scope: {log:"<", fulldisplay:"<", buildnumber:"<", builderid:"<", step:"<"},
            templateUrl: "views/logpreview.html"
            controllerAs: "logpreview"
            bindToController: true
            controller: ["$scope", ($scope) ->

                @settings = bbSettingsService.getSettingsGroup("LogPreview")
                pendingRequest = null
                $scope.$on '$destroy', ->
                    if pendingRequest
                        pendingRequest.cancel()
                loading = $sce.trustAs($sce.HTML, "...")

                unwatchLog = null
                unwatchLines = null
                $scope.$watch "logpreview.fulldisplay", (n, o) =>
                    # Cancel previous requests and stop fetching new lines first
                    if pendingRequest
                        pendingRequest.cancel()
                    if unwatchLines
                        unwatchLines()
                    # Start fetching lines when the preview is visible.
                    if n
                        unwatchLog = $scope.$watch "logpreview.log", fetchLog

                fetchLog = (n, o) =>
                    @log.lines = []
                    if not n?
                        return
                    unwatchLog()
                    if unwatchLines
                        unwatchLines()
                    if @log.type == 'h'
                        pendingRequest = restService.get("logs/#{@log.logid}/contents")
                        pendingRequest.then (content) =>
                            @log.content = $sce.trustAs($sce.HTML, content.logchunks[0].content)
                    else
                        unwatchLines = $scope.$watch "logpreview.log.num_lines", loadLines

                loadLines = (num_lines) =>
                    if @log.lines.length == 0
                        # initial load. only load the last few lines
                        offset = @log.num_lines - @settings.loadlines.value
                        limit = @settings.loadlines.value
                        if offset < 0
                            offset = 0
                            limit = @log.num_lines
                    else
                        # The last element of the line is the last line loaded
                        # This might be actually a loading marker
                        offset = @log.lines[@log.lines.length - 1].number + 1
                        limit = @log.num_lines - offset
                        # if log is advancing very fast no need to load too much lines
                        if limit > @settings.maxlines.value
                            offset = @log.num_lines - @settings.maxlines.value
                            limit = @settings.maxlines.value

                    if limit == 0
                        return

                    # this acts as a marker of the last loaded element
                    # note that several elements can be loading at the same time
                    # as we follow the log updates

                    loading_element =
                        content: loading
                        number: offset + limit - 1
                    @log.lines.push(loading_element)

                    pendingRequest = restService.get("logs/#{@log.logid}/contents",
                                    offset: offset,
                                    limit: limit)
                    pendingRequest.then (content) =>
                        content = content.logchunks[0].content
                        lines = content.split("\n")
                        # there is a trailing '\n' generates an empty line in the end
                        if lines.length > 1
                            lines.pop()
                        number = offset
                        # remove the loading element
                        @log.lines.splice(@log.lines.indexOf(loading_element), 1)
                        for line in lines
                            logclass = "o"
                            if line.length > 0 and (@log.type == 's')
                                logclass = line[0]
                                line = line[1..]
                            # we just push the lines in the end, and will apply sort eventually
                            @log.lines.push
                                content:  $sce.trustAs($sce.HTML, ansicodesService.ansi2html(line))
                                class: "log_" + logclass
                                number: number
                            number += 1
                        @log.lines.sort (a,b) -> a.number - b.number
                        @log.lines.splice(0, @log.lines.length - @settings.maxlines.value)
            ]
            link: (scope, elm, attr) ->
                ansicodesService.injectStyle()
        }
