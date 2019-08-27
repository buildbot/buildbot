/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class LinePlot {
    constructor(d3Service, $filter) {
        return {
            replace: true,
            restrict: 'E',
            scope: {
                data: '=',
                xattr: '@',
                yattr: '@',
                xunit: '@',
                yunit: '@',
                width: '@',
                height: '@'
            },
            template: require('./lineplot.tpl.jade'),
            link(scope, elem, attrs){
                d3Service.get().then(d3 => linkerWithD3(scope, d3, $filter, elem));
            }
        };
    }
}

// an half generic line plot for usage in buildbot views
// we try to be generic enough to try and hope this can be reused for other kind of plot
// while not over-engineer it too much

var linkerWithD3 = function($scope, d3, $filter, elem) {
    let x, xaccessor, xscaledaccessor, y, yaccessor, yscaledaccessor;
    const margin = {
        top: 40,
        right: 20,
        bottom: 30,
        left: 100
    };
    const width = +$scope.width - (margin.left) - (margin.right);
    const height = +$scope.height - (margin.top) - (margin.bottom);
    // set the ranges
    if ($scope.xunit === 'timestamp') {
        x = d3.time.scale().range([
            0,
            width
        ])
        .nice();
        const { xattr } = $scope;
        xaccessor = d => new Date(d[xattr]*1000);
        xscaledaccessor = d => x(new Date(d[xattr]*1000));
    }
    if (($scope.yunit === 'seconds') || ($scope.yunit === 'percent')) {
        y = d3.scale.linear().range([
            height,
            0
        ])
        .nice();
        const { yattr } = $scope;
        yaccessor = d => d[yattr];
        yscaledaccessor = d => y(d[yattr]);
    }

    // define the line
    const valueline = d3.svg.line().x(xscaledaccessor).y(yscaledaccessor).interpolate("bundle");
    const svg = d3.select(elem[0]).attr('width', width + margin.left + margin.right).attr('height', height + margin.top + margin.bottom);
    const base_g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);
    const linepath = base_g.append('path');
    const xaxis_g = base_g.append('g').attr("class", "axis");
    const yaxis_g = base_g.append('g').attr("class", "axis");
    $scope.$watch("data", function(data) {

        if ((data == null)) {
            return;
        }
        // Scale the range of the data
        x.domain(d3.extent(data, xaccessor));
        y.domain([
            d3.min(data, yaccessor),
            d3.max(data, yaccessor)
        ]);
        // Add the valueline path.
        linepath.data([ data ]).attr('class', 'line').attr('d', valueline);
        // Add the X Axis
        const xAxis = d3.svg.axis()
            .scale(x)
            .ticks(5);
        xaxis_g.attr('transform', `translate(0,${height})`).call(xAxis);
        const yAxis = d3.svg.axis()
            .orient('left')
            .scale(y)
            .ticks(3);
        if ($scope.yunit === 'seconds') {
            // duration format is defined in moment.filter.coffee
            yAxis.tickFormat($filter('durationformat'));
        }

        // Add the Y Axis
        yaxis_g.call(yAxis);
    });
};


angular.module('common')
.directive('linePlot', ['d3Service', '$filter', LinePlot]);
