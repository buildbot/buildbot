name = 'buildbot.waterfall_view'
dependencies = [
    'ui.router'
    'buildbot.common'
    'ngAnimate'
]

# Register new module
m = angular.module name, dependencies
if not window.__karma__?
    angular.module('app').requires.push(name)

# Register new state
m.config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'waterfall'

        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'Waterfall View'

        # Register new state
        state =
            controller: "#{name}Controller"
            controllerAs: "w"
            templateUrl: "waterfall_view/views/#{name}.html"
            name: name
            url: "/#{name}"
            data: cfg

        $stateProvider.state(state)
]

m.controller 'waterfallController',
    ['$scope', '$q', '$window', '$modal', 'buildbotService', 'd3Service', 'dataService', 'scaleService', class
        self = null
        constructor: (@$scope, $q, @$window, @$modal, @buildbotService, d3Service, @dataService, scaleService) ->
            self = @

            # Show loading spinner
            @loading = true

            # Load data (builds and builders)
            # TODO lazy load builds
            builds = @buildbotService.all('builds').getList()
            builders = @buildbotService.all('builders').getList()

            $q.all([d3Service.get(), builders, builds]).then ([@d3, @builders, @builds]) =>

                # Create a scale object
                @scale = new scaleService(@d3)

                @groups = @dataService.getGroups(@builders, @builds)
                @dataService.addStatus(@builders)

                # Select containers
                container = @d3.select('.svg-container')
                header = @d3.select('.header-content')

                # Options and settings
                @o =
                    margin:
                        top: 15
                        right: 20
                        bottom: 20
                        left: 70

                    gap: 20

                    # SVG width and height
                    getWidth: -> parseInt container.style('width').replace('px', ''), 10
                    getHeight: -> parseInt container.style('height').replace('px', ''), 10

                    # Inner width and height
                    getInnerWidth: -> @getWidth() - @margin.left - @margin.right
                    getInnerHeight: -> @getHeight() - @margin.top - @margin.bottom

                    # Header height
                    getHeaderHeight: -> parseInt header.style('height').replace('px', ''), 10

                    # Minimum builder column width
                    minColumnWidth: 40

                    # Y axis tick values
                    ticks: []
                    addTicks: (build) ->
                        y = self.scale.getY(self.groups, @gap, @getInnerHeight())
                        @ticks = @ticks.concat [y(build.complete_at), y(build.started_at)]
                    removeTicks: ->
                        @ticks = []
                    getTickValues: ->
                        y = self.scale.getY(self.groups, @gap, @getInnerHeight())
                        extents = []
                        self.groups?.forEach (group) =>
                            extents.push y(group.min)
                            extents.push y(group.max)
                        extents.concat(@ticks)

                    # Y axis time format
                    timeFormat: '%x %I:%M'

                # Set the content width to the window width
                @setWidth(@$window.innerWidth)

                # Set the height of the container
                height = do =>
                    h = 0
                    for group in @groups
                        h += group.max - group.min
                    return h
                container.style('height', "#{height}px")
                        
                # Render the waterfall
                @render(header, container)
                # Hide the spinner
                @loading = false

        # Returns the result string of a builder, build or step
        result: (b) ->
            if b.complete == false and b.started_at > 0
                result = 'pending'
            else
                switch b.results
                    when 0 then result = 'success'
                    when 1 then result = 'warnings'
                    when 2 then result = 'failure'
                    when 3 then result = 'skipped'
                    when 4 then result = 'exception'
                    when 5 then result = 'cancelled'
                    else result = 'unknown'
            return result

        drawXAxis: ->
            header = @header
            x = @scale.getX(@builders, @o.getInnerWidth())
            builderName = @scale.getBuilderName(@builders)
            color = @result

            # Remove old axis
            header.select('.axis.x')

            # Top axis shows builder names
            xAxis = @d3.svg.axis()
                .scale(x)
                .orient('top')
                .tickFormat(builderName)

            xAxisSelect = header.append('g')
                .attr('class', 'axis x')
                .call(xAxis)

            # Rotate names
            xAxisSelect.selectAll('text')
                .style('text-anchor', 'start')
                .attr('transform', 'translate(0, -5) rotate(-60)')
                .attr('dy', '.75em')

            # Rotate tick lines
            xAxisSelect.selectAll('line')
                .data(@builders)
                .attr('transform', 'rotate(90)')
                .attr('x1', 0)
                .attr('x2', 0)
                .attr('y1', x.rangeBand() / 2)
                .attr('y2', - x.rangeBand() / 2)
                .attr('class', color)
                .classed('stroke', true)

        drawYAxis: ->
            element = @chart
            i = @d3.scale.linear()
            y = @scale.getY(@groups, @o.gap, @o.getInnerHeight())
            o = @o
            d3 = @d3

            # Remove old axis
            element.select('.axis.y').remove()

            tickFormat = (coordinate) ->
                timestamp = y.invert(coordinate)
                date = new Date(timestamp * 1000)
                format = d3.time.format(o.timeFormat)
                format(date)

            yAxis = d3.svg.axis()
                .scale(i)
                .orient('left')
                .tickValues(o.getTickValues())
                .tickFormat(tickFormat)

            lineBreak = ->
                e = self.d3.select(@)
                words = e.text().split(' ')
                e.text('')

                for word, i in words
                    text = e.append('tspan').text(word)
                    if i isnt 0
                        x = e.attr('x')
                        text.attr('x', x).attr('dy', i * 10)

            yAxis = element.append('g')
                .attr('class', 'axis y')
                .call(yAxis)

            yAxis.selectAll('text').each(lineBreak)

            yAxis.selectAll('.tick')
                .append('line')
                    .attr('x2', o.getInnerWidth())
                    .attr('stroke', '#3498db')
                    .attr('stroke-dasharray', '5, 10')

        drawBuilds: ->
            element = @chart
            x = @scale.getX(@builders, @o.getInnerWidth())
            y = @scale.getY(@groups, @o.gap, @o.getInnerHeight())
            o = @o
            color = @result

            # Set width on resize
            element.selectAll('.builder')
                .attr('transform', (builder) => "translate(#{x(builder.builderid)}, 0)")
            element.selectAll('.build rect').attr('width', x.rangeBand())
            element.selectAll('.build .id').attr('x', x.rangeBand() / 2)

            # Create builder groups
            builders = element.selectAll('.builder')
                .data(@builders).enter()
                .append('g')
                    .attr('class', 'builder')
                    .attr('transform', (builder) => "translate(#{x(builder.builderid)}, 0)")

            # Create build group for each build
            data = (builder) -> builder.builds
            key = (build) -> build.buildid
            builds = builders.selectAll('.build')
                .data(data, key).enter()
                .append('g')
                    .attr('class', 'build')
                    .attr('transform', (build) -> "translate(0, #{y(build.complete_at)})")

            # Draw rectangle for each build
            builds.append('rect')
                .attr('class', color)
                .attr('width', x.rangeBand())
                .attr('height', (build) -> y(build.started_at) - y(build.complete_at))
                .classed('fill', true)

            # Optional: grey rectangle below buildids
            ###
            builds.append('rect')
                .attr('y', -14)
                .attr('width', x.rangeBand())
                .attr('height', 14)
                .style('fill', '#BBB')
            ###

            # Draw text over builds
            builds.append('text')
                .attr('class', 'id')
                .attr('x', x.rangeBand() / 2)
                .attr('y', -3)
                .text((build) -> build.buildid)

            # Event actions
            mouseOver = (build) ->
                e = self.d3.select(@)
                mouse = self.d3.mouse(@)
                o.addTicks(build)
                self.drawYAxis()

                # Move build and builder to front
                e.each ->
                    p = self.d3.select(@parentNode)
                    @parentNode.appendChild(@)
                    p.each -> @parentNode.appendChild(@)

                # Show tooltip on the left or on the right
                r = build.builderid < self.builders.length / 2

                # Create tooltip
                height = 40
                points = ->
                    if r
                        return "20,0 0,#{height / 2} 20,#{height} 170,#{height} 170,0"
                    return "150,0 170,#{height / 2} 150,#{height} 0,#{height} 0,0"
                tooltip = e.append('g')
                    .attr('class', 'svg-tooltip')
                    .attr('transform', "translate(#{mouse[0]}, #{mouse[1]})")
                    .append('g')
                        .attr('class', 'tooltip-content')
                        .attr('transform', "translate(#{if r then 5 else -175}, #{- height / 2})")

                tooltip.append('polygon')
                    .attr('points', points())

                # Load steps
                build.all('steps').getList().then (buildsteps) ->

                    # Resize the tooltip
                    height = buildsteps.length * 15 + 7
                    tooltip.transition().duration(100)
                        .attr('transform', "translate(#{if r then 5 else -175}, #{- height / 2})")
                        .select('polygon')
                            .attr('points', points())

                    duration = (step) ->
                        d = new Date((step.complete_at - step.started_at) * 1000)
                        "#{d / 1000}s"
                    tooltip.selectAll('.buildstep')
                        .data(buildsteps)
                        .enter().append('g')
                            .attr('class', 'buildstep')
                            # Add text
                            .append('text')
                                .attr('y', (step, i) -> 15 * (i + 1))
                                .attr('x', if r then 30 else 10)
                                .attr('class', color)
                                .classed('fill', true)
                                .transition().delay(100)
                                # Text format
                                .text((step, i) -> "#{i + 1}. #{step.name} (#{duration(step)})")

            mouseMove = (build) ->
                e = self.d3.select(@)

                # Move the tooltip to the mouse position
                mouse = self.d3.mouse(@)
                e.select('.svg-tooltip')
                    .attr('transform', "translate(#{mouse[0]}, #{mouse[1]})")

            mouseOut = (build) ->
                e = self.d3.select(@)
                o.removeTicks()
                self.drawYAxis()

                # Remove tooltip
                e.selectAll('.svg-tooltip').remove()

            click = (build) ->
                # Open modal on click
                modal = self.$modal.open
                    templateUrl: 'waterfall_view/views/modal.html'
                    controller: 'modalController as modal'
                    windowClass: 'modal-small'
                    resolve:
                        selectedBuild: -> build

            # Add event listeners
            builds
                .on('mouseover', mouseOver)
                .on('mousemove', mouseMove)
                .on('mouseout', mouseOut)
                .on('click', click)

        render: (header, container) ->

            # Delete all element
            container.selectAll('*').remove()
            header.selectAll('*').remove()

            # Create svg elements
            svg = container.append('svg')
            headerSvg = header.append('svg')

            # Create chart
            @chart = svg.append('g')
                .attr('transform', "translate(#{@o.margin.left}, #{@o.margin.top})")
                .attr('class', 'chart')

            # Create header
            @header = headerSvg.append('g')
                .attr('transform', "translate(#{@o.margin.left}, #{@o.getHeaderHeight()})")

            @drawXAxis()
            @drawYAxis()
            @drawBuilds()

            # Execute on resize
            angular.element(@$window).bind 'resize', =>
                @setWidth(@$window.innerWidth)
                @$scope.$apply()
                @drawBuilds()
                @drawXAxis()
                @drawYAxis()

            # Draw new builds on change
            @$scope.$watch @builders, =>
                @groups = @dataService.getGroups(@builders, @builds)
                @dataService.addStatus(@builders)
                @drawBuilds()
            , true

        setWidth: (width) ->
            @cellWidth = "#{100 / @builders.length}%"
            if width / @builders.length > @o.minColumnWidth
                @width = '100%'
            else
                @width = "#{@builders.length * @o.minColumnWidth}px"

    ]