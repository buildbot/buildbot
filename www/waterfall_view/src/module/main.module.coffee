# Register new module
class WaterfallView extends App
    constructor: -> return [
        'ui.router'
        'ngAnimate'
        'common'
        'guanlecoja.ui'
    ]

class Waterfall extends Controller
    self = null
    constructor: (@$scope, $q, @$window, @$modal, @buildbotService, d3Service, @dataService, scaleService, config) ->
        self = @

        # Show the loading spinner
        @loading = true

        # Waterfall configuration
        cfg = config.plugins.waterfall_view
        @c =
            # Margins around the chart
            margin:
                top: cfg.margin?.top or 15
                right: cfg.margin?.right or 20
                bottom: cfg.margin?.bottom or 20
                left: cfg.margin?.left or 70

            # Gap between groups (px)
            gap: cfg.gap or 30

            # Minimum builder column width (px)
            minColumnWidth: cfg.minColumnWidth or 40

            # Y axis time format (new line: ^)
            timeFormat: cfg.timeFormat or '%x^%H:%M'

            # Lazy load limit
            limit: cfg.limit or 40

            # Idle time threshold in unix time stamp (eg. 300 = 5 min)
            threshold: cfg.threshold or 300

            # Grey rectangle below buildids
            buildidBackground: cfg.buildidBackground or false

        # Load data (builds and builders)
        builders = @buildbotService.all('builders').bind(@$scope)
        builds = @buildbotService.some('builds', {limit: @c.limit, order: '-complete_at'}).bind(@$scope)

        $q.all([d3Service.get(), builders, builds]).then ([@d3, @builders, @builds]) =>

            # Create a scale object
            @scale = new scaleService(@d3)

            # Create groups and add builds to builders
            @groups = @dataService.getGroups(@builders, @builds, @c.threshold)
            # Add builder status to builders
            @dataService.addStatus(@builders)

            # Select containers
            @waterfall = @d3.select('.waterfall')
            @container = @waterfall.select('.svg-container')
            @header = @waterfall.select('.header-content')
            # Append svg elements to the containers
            @createElements()

            # Render the waterfall
            @render()
            # Hide the spinner
            @loading = false

            # Render on resize
            @$scope.$watch(
                => @waterfall.style('width')
            ,
                (n, o) => if n != o then @render()
            , true
            )
            angular.element(@$window).bind 'resize', => @render()

            # Update view on data change
            @$scope.$watch('builds', ((builds) =>
                if builds? and @builds.length isnt builds.length
                    @builds = builds
                    @groups = @dataService.getGroups(@builders, @builds, @c.threshold)
                    @dataService.addStatus(@builders)
                    @render()
                ), true)

            # Lazy load builds on scroll
            containerParent = @container.node().parentNode
            onScroll = =>
                if  @getHeight() - containerParent.scrollTop < 1000
                    # Unbind scroll listener to prevent multiple execution before new data are received
                    angular.element(containerParent).unbind('scroll')
                    @loadMore().then (builds) =>
                        if builds? and @builds.length isnt builds.length
                            # $scope.$watch renders the new data
                            # Rebind scroll listener
                            angular.element(containerParent).bind 'scroll', onScroll
                        # All builds are rendered, unbind event listener
                        else angular.element(containerParent).unbind('scroll')

            # Bind scroll event listener
            angular.element(containerParent).bind 'scroll', onScroll

    ###
    # Load more builds
    ###
    loadMore: ->
        @buildbotService.some('builds', {limit: @builds.length + @c.limit, order: '-complete_at'}).bind(@$scope)
        # $scope.$watch renders the new data

    ###
    # Create svg elements for chart and header, append svg groups
    ###
    createElements: ->

        # Remove any unwanted elements first
        @container.selectAll('*').remove()
        @header.selectAll('*').remove()

        @chart = @container.append('svg')
            .append('g')
                .attr('transform', "translate(#{@c.margin.left}, #{@c.margin.top})")
                .attr('class', 'chart')

        @header = @header.append('svg')
            .append('g')
                .attr('transform', "translate(#{@c.margin.left}, #{@getHeaderHeight()})")
                .attr('class', 'header')

    ###
    # Get the container width
    ###
    getWidth: -> parseInt @container.style('width').replace('px', ''), 10

    ###
    # Set the content width
    ###
    setWidth: ->
        if @c.minColumnWidth > 0
            columnWidth = (@$window.innerWidth - @c.margin.right - @c.margin.left) / @builders.length

            wider = @c.minColumnWidth <= columnWidth

            width =
                if wider then '100%'
                else
                    "#{@builders.length * @c.minColumnWidth + @c.margin.right + @c.margin.left}px"

            @waterfall.select('.inner-content').style('width', width)
            @waterfall.select('.header-content').style('width', width)

        else
            @$log.error "Bad column width configuration\n\t min: #{@c.minColumnWidth}"

    ###
    # Get the container height
    ###
    getHeight: -> parseInt @container.style('height').replace('px', ''), 10

    ###
    # Set the container height
    ###
    setHeight: ->
        h = - @c.gap
        for group in @groups
            h += (group.max - group.min + @c.gap)
        height = h + @c.margin.top + @c.margin.bottom
        if height < parseInt @waterfall.style('height').replace('px', ''), 10
            @loadMore()
        @container.style('height', "#{height}px")

    ###
    # Returns content width
    ###
    getInnerWidth: ->
        width = @getWidth()
        return width - @c.margin.left - @c.margin.right

    ###
    # Returns content height
    ###
    getInnerHeight: ->
        height = @getHeight()
        return height- @c.margin.top - @c.margin.bottom

    ###
    # Returns headers height
    ###
    getHeaderHeight: -> parseInt @header.style('height').replace('px', ''), 10

    ###
    # Returns the result string of a builder, build or step
    ###
    getResultClassFromThing: (b) ->
        if not b.complete and b.started_at >= 0
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

    ###
    # Draw x axis
    ###
    drawXAxis: ->
        x = @scale.getX(@builders, @getInnerWidth())
        builderName = @scale.getBuilderName(@builders)

        # Remove old axis
        @header.select('.axis.x').remove()
        # Select axis
        axis = @header.append('g')
            .attr('class', 'axis x')

        # Remove previous elements
        axis.selectAll('*').remove()

        # Top axis shows builder names
        xAxis = @d3.svg.axis()
            .scale(x)
            .orient('top')
            .tickFormat(builderName)

        xAxisSelect = axis.call(xAxis)

        # Add link
        link = (builderid) ->
            p = self.d3.select(@parentNode)
            a = p.append('a')
                .attr('xlink:href', "#/builders/#{builderid}")
            a.node().appendChild(@)

        # Rotate text
        xAxisSelect.selectAll('text')
            .style('text-anchor', 'start')
            .attr('transform', 'translate(0, -5) rotate(-60)')
            .attr('dy', '.75em')
            .each(link)

        # Rotate tick lines
        xAxisSelect.selectAll('line')
            .data(@builders)
            .attr('transform', 'rotate(90)')
            .attr('x1', 0)
            .attr('x2', 0)
            .attr('y1', x.rangeBand() / 2)
            .attr('y2', - x.rangeBand() / 2)
            .attr('class', self.getResultClassFromThing)
            .classed('stroke', true)

    # Y axis tick values
    ticks: []
    addTicks: (build) ->
        y = @scale.getY(@groups, @c.gap, @getInnerHeight())
        @ticks = @ticks.concat [y(build.complete_at), y(build.started_at)]
    removeTicks: -> @ticks = []

    ###
    # Draw y axis
    ###
    drawYAxis: ->
        i = @d3.scale.linear()
        y = @scale.getY(@groups, @c.gap, @getInnerHeight())

        # Remove old axis
        @chart.select('.axis.y').remove()
        axis = @chart.append('g')
            .attr('class', 'axis y')

        # Stay on left on horizontal scrolling
        axis.attr('transform', "translate(#{@waterfall.node().scrollLeft}, 0)")
        @waterfall.on 'scroll', ->  yAxis.attr('transform', "translate(#{@scrollLeft}, 0)")

        # White background
        axis.append('rect')
            .attr('x', - @c.margin.left)
            .attr('y', - @c.margin.top)
            .attr('width', @c.margin.left)
            .attr('height', @getHeight())
            .style('fill', '#fff')

        ticks = @ticks
        for group in @groups
            ticks = ticks.concat [y(group.min), y(group.max)]

        # Y axis tick format
        tickFormat = (coordinate) =>
            timestamp = y.invert(coordinate)
            date = new Date(timestamp * 1000)
            format = @d3.time.format(@c.timeFormat)
            format(date)

        yAxis = @d3.svg.axis()
            .scale(i)
            .orient('left')
            .tickValues(ticks)
            .tickFormat(tickFormat)

        yAxis = axis.call(yAxis)

        # Break text on ^ character
        lineBreak = ->
            e = self.d3.select(@)
            words = e.text().split('^')
            e.text('')

            for word, i in words
                text = e.append('tspan').text(word)
                if i isnt 0
                    x = e.attr('x')
                    text.attr('x', x).attr('dy', i * 10)
        yAxis.selectAll('text').each(lineBreak)

        dasharray = (tick) => if tick in @ticks then '2, 5' else '2, 1'

        yAxis.selectAll('.tick')
            .append('line')
                .attr('x2', @getInnerWidth())
                .attr('stroke-dasharray', dasharray)

    drawBuilds: ->
        x = @scale.getX(@builders, @getInnerWidth())
        y = @scale.getY(@groups, @c.gap, @getInnerHeight())

        # Remove previous elements
        @chart.selectAll('.builder').remove()

        # Create builder columns
        builders = @chart.selectAll('.builder')
            .data(@builders).enter()
            .append('g')
                .attr('class', 'builder')
                .attr('transform', (builder) -> "translate(#{x(builder.builderid)}, 0)")

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
            .attr('class', self.getResultClassFromThing)
            .attr('width', x.rangeBand())
            .attr('height', (build) -> y(build.started_at) - y(build.complete_at))
            .classed('fill', true)

        # Optional: grey rectangle below buildids
        if @c.buildidBackground
            builds.append('rect')
                .attr('y', -15)
                .attr('width', x.rangeBand())
                .attr('height', 15)
                .style('fill', '#ccc')

        # Draw text over builds
        builds.append('text')
            .attr('class', 'id')
            .attr('x', x.rangeBand() / 2)
            .attr('y', -3)
            .text((build) -> build.number)

        # Add event listeners
        builds
            .on('mouseover', @mouseOver)
            .on('mousemove', @mouseMove)
            .on('mouseout', @mouseOut)
            .on('click', @click)

    ###
    # Event actions
    ###
    mouseOver: (build) ->
        e = self.d3.select(@)
        mouse = self.d3.mouse(@)
        self.addTicks(build)
        self.drawYAxis()

        # Move build and builder to front
        p = self.d3.select(@parentNode)
        @parentNode.appendChild(@)
        p.each -> @parentNode.appendChild(@)

        # Show tooltip on the left or on the right
        r = build.builderid < self.builders.length / 2

        # Create tooltip
        height = 40
        points = ->
            if r then "20,0 0,#{height / 2} 20,#{height} 170,#{height} 170,0"
            else "150,0 170,#{height / 2} 150,#{height} 0,#{height} 0,0"
        tooltip = e.append('g')
            .attr('class', 'svg-tooltip')
            .attr('transform', "translate(#{mouse[0]}, #{mouse[1]})")
            .append('g')
                .attr('class', 'tooltip-content')
                .attr('transform', "translate(#{if r then 5 else -175}, #{- height / 2})")

        tooltip.append('polygon')
            .attr('points', points())

        # Load steps
        build.all('steps').bind(self.$scope).then (buildsteps) ->

            # Resize the tooltip
            height = buildsteps.length * 15 + 7
            tooltip.transition().duration(100)
                .attr('transform', "translate(#{if r then 5 else -175}, #{- height / 2})")
                .select('polygon')
                    .attr('points', points())

            duration = (step) ->
                d = new Date((step.complete_at - step.started_at) * 1000)
                if d > 0 then "(#{d / 1000}s)" else ''
            tooltip.selectAll('.buildstep')
                .data(buildsteps)
                .enter().append('g')
                .attr('class', 'buildstep')
                # Add text
                .append('text')
                    .attr('y', (step, i) -> 15 * (i + 1))
                    .attr('x', if r then 30 else 10)
                    .attr('class', self.getResultClassFromThing)
                    .classed('fill', true)
                    .transition().delay(100)
                    # Text format
                    .text((step, i) -> "#{i + 1}. #{step.name} #{duration(step)}")

    mouseMove: (build) ->
        e = self.d3.select(@)

        # Move the tooltip to the mouse position
        mouse = self.d3.mouse(@)
        e.select('.svg-tooltip')
            .attr('transform', "translate(#{mouse[0]}, #{mouse[1]})")

    mouseOut: (build) ->
        e = self.d3.select(@)
        self.removeTicks()
        self.drawYAxis()

        # Remove tooltip
        e.selectAll('.svg-tooltip').remove()

    click: (build) ->
        # Open modal on click
        modal = self.$modal.open
            templateUrl: 'waterfall_view/views/modal.html'
            controller: 'waterfallModalController as modal'
            windowClass: 'modal-small'
            resolve:
                selectedBuild: -> build

    ###
    # Render the waterfall view
    ###
    render: ->

        # Set the content width
        @setWidth()

        # Set the height of the container
        @setHeight()

        # Draw the waterfall
        @drawBuilds()
        @drawXAxis()
        @drawYAxis()
