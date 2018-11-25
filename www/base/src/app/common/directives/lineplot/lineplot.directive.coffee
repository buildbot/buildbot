class LinePlot extends Directive('common')
    constructor:  (d3Service, $filter) ->
        return {
            replace: true
            restrict: 'E'
            scope: {
                data: '=',
                xattr: '@'
                yattr: '@'
                xunit: '@'
                yunit: '@'
                width: '@'
                height: '@'
            }
            templateUrl: 'views/lineplot.html'
            link: (scope, elem, attrs)->
                d3Service.get().then (d3) -> linkerWithD3(scope, d3, $filter, elem)
        }

# an half generic line plot for usage in buildbot views
# we try to be generic enough to try and hope this can be reused for other kind of plot
# while not over-engineer it too much

linkerWithD3= ($scope, d3, $filter, elem) ->
    margin =
        top: 40
        right: 20
        bottom: 30
        left: 100
    width = +$scope.width - (margin.left) - (margin.right)
    height = +$scope.height - (margin.top) - (margin.bottom)
    # set the ranges
    if $scope.xunit == 'timestamp'
        x = d3.time.scale().range([
            0
            width
        ])
        .nice()
        xattr = $scope.xattr
        xaccessor = (d) -> new Date(d[xattr]*1000)
        xscaledaccessor = (d) -> x(new Date(d[xattr]*1000))
    if $scope.yunit == 'seconds' or $scope.yunit == 'percent'
        y = d3.scale.linear().range([
            height
            0
        ])
        .nice()
        yattr = $scope.yattr
        yaccessor = (d) -> d[yattr]
        yscaledaccessor = (d) -> y(d[yattr])

    # define the line
    valueline = d3.svg.line().x(xscaledaccessor).y(yscaledaccessor).interpolate("bundle")
    svg = d3.select(elem[0]).attr('width', width + margin.left + margin.right).attr('height', height + margin.top + margin.bottom)
    base_g = svg.append('g').attr('transform', 'translate(' + margin.left + ',' + margin.top + ')')
    linepath = base_g.append('path')
    xaxis_g = base_g.append('g').attr("class", "axis")
    yaxis_g = base_g.append('g').attr("class", "axis")
    $scope.$watch "data", (data) ->

        if not data?
            return
        # Scale the range of the data
        x.domain d3.extent(data, xaccessor)
        y.domain [
            d3.min(data, yaccessor),
            d3.max(data, yaccessor)
        ]
        # Add the valueline path.
        linepath.data([ data ]).attr('class', 'line').attr 'd', valueline
        # Add the X Axis
        xAxis = d3.svg.axis()
            .scale(x)
            .ticks(5)
        xaxis_g.attr('transform', 'translate(0,' + height + ')').call xAxis
        yAxis = d3.svg.axis()
            .orient('left')
            .scale(y)
            .ticks(3)
        if $scope.yunit == 'seconds'
            # duration format is defined in moment.filter.coffee
            yAxis.tickFormat $filter('durationformat')

        # Add the Y Axis
        yaxis_g.call yAxis
    return
