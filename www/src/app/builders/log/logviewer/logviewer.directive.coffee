# logviewer. This directive uses jquery for simplicity
angular.module('buildbot.builders').directive 'logviewer',
['$log', '$window', 'buildbotService', "$timeout", "$sce",
    ($log, $window, buildbotService, $timeout, $sce) ->
        $window = angular.element($window)

        directive = ->
            self =
            num_lines: 0
            auto_scroll: true
            lines: []
            onScroll: (e) ->
                $timeout(self.maybeLoadMore, 1)
                return null

            setHeight: (elm) ->
                height = $window.height() - elm.offset().top - 20
                elm.css({height: height + "px"})

            setNumLines: (num_lines) ->
                if num_lines > self.num_lines
                    for i in [self.num_lines..num_lines - 1]
                        self.lines.push
                            content: ".\n"
                            class: "log_o"
                    self.num_lines = num_lines
                    if self.auto_scroll
                        $timeout(self.autoScroll, 1)
                    else
                        $timeout(self.maybeLoadMore, 1)

            autoScroll: ->
                self.elm.scrollTop(self.raw.scrollHeight)
                $timeout(self.maybeLoadMore, 1)

            getViewPortLineBoundary: ->
                line_height = self.raw.scrollHeight / self.num_lines

                firstline = Math.round(self.raw.scrollTop / line_height) - 1
                lastline = firstline + Math.round(self.elm.height() / line_height) + 1

                if firstline < 0
                    firstline = 0

                if lastline >= self.num_lines
                    lastline = self.num_lines - 1

                firstline:firstline
                lastline:lastline
                lines_per_page: lastline - firstline

            maybeLoadMore: ->
                if self.loading
                    return
                if self.scope.log.type != 's'
                    return
                b = self.getViewPortLineBoundary()

                if b.lastline > self.num_lines - 3
                    self.auto_scroll = true
                else
                    self.auto_scroll = false

                # if search mode, then we need to load everything
                if self.scope.searchText?.length > 0
                    b.firstline = 0
                    b.lastline = self.num_lines - 1

                lines = self.lines

                # tighten refresh boundary to the part that is not loaded
                # from top...
                while lines[b.firstline].loaded and b.firstline < b.lastline
                    b.firstline += 1

                # and from bottom...
                while lines[b.lastline].loaded and b.firstline < b.lastline
                    b.lastline -= 1

                # hurray! everything is already there!
                if b.firstline == b.lastline
                    return

                # load one more page up if the previous line is not loaded
                if b.firstline > 0 and not lines[b.firstline - 1].loaded
                    b.firstline -= b.lines_per_page
                    if b.firstline < 0
                        b.firstline = 0

                # load one more page down if the previous page is not loaded
                if b.lastline < self.num_lines - 1 and not lines[b.lastline + 1].loaded
                    b.lastline += b.lines_per_page
                    if b.lastline > self.num_lines - 1
                        b.lastline = self.num_lines - 1

                spec =
                    offset: b.firstline
                    limit: b.lastline - b.firstline
                self.loading = true
                self.log.all('contents').getList(spec).then (content) ->
                    self.loading = false
                    content = content[0]
                    offset = spec.offset
                    for line in content.content.split("\n")
                        logclass = "o"
                        if line.length > 0
                            logclass = line[0]
                            line = line[1..]
                        lines[offset] =
                            content: line
                            class: "log_" + logclass
                            loaded: true
                        offset += 1
                    self.maybeLoadMore()
                return null

            updateLog: ->
                self.log.bind(self.scope)
                .then (log) ->
                    if log.type == 's'
                        self.scope.$watch "log.num_lines", ->
                            self.setNumLines(log.num_lines)
                    else
                        self.log.all('contents').getList().then (content) ->
                            self.scope.content = $sce.trustAs($sce.HTML, content[0].content)
            link: (scope, elm, attr) ->
                elm = elm.children("pre")
                self.setHeight(elm)
                self.elm = elm
                self.raw = elm[0]
                $window.resize(-> self.setHeight(elm))
                elm.bind("scroll", self.onScroll)
                scope.lines = self.lines
                self.scope = scope
                unwatch = scope.$watch "logid", (n, o) ->
                    if n?
                        self.logid = n
                        unwatch()
                        self.log = buildbotService.one('logs', self.logid)
                        self.updateLog()

                # for the search feature, we need to load everything
                scope.$watch "searchText", (n, o) ->
                    if n? and n?.length > 0
                        self.maybeLoadMore()
                return null

        replace: true
        transclude: true
        restrict: 'E'
        scope: {logid:"="}
        templateUrl: "views/logviewer.html"
        link: (scope, elm, attr) ->
            self = directive()
            self.link(scope, elm, attr)
    ]
