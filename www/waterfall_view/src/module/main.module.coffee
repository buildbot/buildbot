# Register new module
class WaterfallView extends App
    constructor: -> return [
        'ui.router'
        'ngAnimate'
        'guanlecoja.ui'
        'bbData'
    ]


class Waterfall extends Controller
    self = null
    constructor: (@$scope, $q, $timeout, @$window, @$log,
                  @$uibModal, dataService, d3Service, @dataProcessorService,
                  scaleService, @bbSettingsService) ->
        self = this

        # Show the loading spinner
        @loading = true
        @dataAccessor = dataService.open().closeOnDestroy(@$scope)
        # Get Waterfall settings
        @s = @bbSettingsService.getSettingsGroup('Waterfall')
        @c =
            # Margins around the chart
            margin:
                top: 15
                right: 20
                bottom: 20
                left: 70

            # Gap between groups (px)
            gap: 30

            # Default vertical scaling
            scaling: @s.scaling_waterfall.value

            # Minimum builder column width (px)
            minColumnWidth: @s.min_column_width_waterfall.value

            # Y axis time format (new line: ^)
            timeFormat: '%x^%H:%M'

            # Lazy load limit
            limit: @s.lazy_limit_waterfall.value

            # Idle time threshold in unix time stamp (eg. 300 = 5 min)
            threshold: @s.idle_threshold_waterfall.value

            # Grey rectangle below buildids
            buildidBackground: @s.number_background_waterfall.value

        # Load data (builds and builders)
        @$scope.builders = @builders = @dataAccessor.getBuilders(order: 'name')
        @$scope.builders.queryExecutor.isFiltered = (v) ->
            return not v.masterids? or v.masterids.length > 0
        @buildLimit = @c.limit
        @$scope.builds = @builds = @dataAccessor.getBuilds({limit: @buildLimit, order: '-complete_at'})

        d3Service.get().then (@d3) =>

            # Create a scale object
            @scale = new scaleService(@d3)

            # Create groups and add builds to builders
            @groups = @dataProcessorService.getGroups(@builders, @builds, @c.threshold)
            # Add builder status to builders
            @dataProcessorService.addStatus(@builders)

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
            @loadingMore = false
            @builds.onChange = @builders.onChange = @renderNewData


            # Lazy load builds on scroll
            containerParent = @container.node().parentNode
            onScroll = =>
                if not @loadingMore and @getHeight() - containerParent.scrollTop < 1000
                    @loadingMore = true
                    @loadMore()

            # Bind scroll event listener
            angular.element(containerParent).bind 'scroll', onScroll

            @$window.onkeydown = (e) =>
                # +
                if e.key is '+'
                    e.preventDefault()
                    @incrementScaleFactor()
                    @render()
                # -
                if e.key is '-'
                    e.preventDefault()
                    @decrementScaleFactor()
                    @render()

    ###
    # Increment and decrement the scale factor
    ###
    incrementScaleFactor: ->
        @c.scaling *= 1.5
        @s.scaling_waterfall.value *= 1.5
        @bbSettingsService.save()

    decrementScaleFactor: ->
        @c.scaling /= 1.5
        @s.scaling_waterfall.value /= 1.5
        @bbSettingsService.save()

    ###
    # Load more builds
    ###
    loadMore: ->
        if @builds.length < @buildLimit
            # last query returned less build than expected, so we went to the beginning of time
            # no need to query again
            return
        @buildLimit = @builds.length + @c.limit
        builds = @dataAccessor.getBuilds({limit: @buildLimit, order: '-complete_at'})
        builds.onChange = (builds) =>
            @builds.close()  # force close the old collection's auto-update
            @builds = builds
            # renders the new data
            builds.onChange = @renderNewData
            builds.onChange()

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
        h = -@c.gap
        for group in @groups
            h += (group.max - group.min + @c.gap)
        height = h * @c.scaling + @c.margin.top + @c.margin.bottom
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
        return height - @c.margin.top - @c.margin.bottom

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
            a.node().appendChild(this)

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
            .attr('y1', x.rangeBand(1) / 2)
            .attr('y2', -x.rangeBand(1) / 2)
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
            .attr('x', -@c.margin.left)
            .attr('y', -@c.margin.top)
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
            e = self.d3.select(this)
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
        max = (a, b) ->
            if (a > b)
                return a
            return b
        # Draw rectangle for each build
        builds.append('rect')
            .attr('class', self.getResultClassFromThing)
            .attr('width', x.rangeBand(1))
            .attr('height', (build) -> max(10, Math.abs(y(build.started_at) - y(build.complete_at))))
            .classed('fill', true)

        # Optional: grey rectangle below buildids
        if @c.buildidBackground
            builds.append('rect')
                .attr('y', -15)
                .attr('width', x.rangeBand(1))
                .attr('height', 15)
                .style('fill', '#ccc')

        # Draw text over builds
        builds.append('text')
            .attr('class', 'id')
            .attr('x', x.rangeBand(1) / 2)
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
        e = self.d3.select(this)
        mouse = self.d3.mouse(this)
        self.addTicks(build)
        self.drawYAxis()

        # Move build and builder to front
        p = self.d3.select(@parentNode)
        @parentNode.appendChild(this)
        p.each -> @parentNode.appendChild(this)

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
        build.loadSteps().onChange = (buildsteps) ->
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
        e = self.d3.select(this)

        # Move the tooltip to the mouse position
        mouse = self.d3.mouse(this)
        e.select('.svg-tooltip')
            .attr('transform', "translate(#{mouse[0]}, #{mouse[1]})")

    mouseOut: (build) ->
        e = self.d3.select(this)
        self.removeTicks()
        self.drawYAxis()

        # Remove tooltip
        e.selectAll('.svg-tooltip').remove()

    click: (build) ->
        # Open modal on click
        modal = self.$uibModal.open
            templateUrl: 'waterfall_view/views/modal.html'
            controller: 'waterfallModalController as modal'
            windowClass: 'modal-small'
            resolve:
                selectedBuild: -> build

    renderNewData: =>
        @groups = @dataProcessorService.getGroups(@builders, @builds, @c.threshold)
        @dataProcessorService.addStatus(@builders)
        @render()
        @loadingMore = false

    ###
    # Render the waterfall view
    ###
    render: ->

        containerParent = @container.node().parentNode
        y = @scale.getY(@groups, @c.gap, @getInnerHeight())
        time = y.invert(containerParent.scrollTop)

        # Set the content width
        @setWidth()

        # Set the height of the container
        @setHeight()

        # Draw the waterfall
        @drawBuilds()
        @drawXAxis()
        @drawYAxis()
