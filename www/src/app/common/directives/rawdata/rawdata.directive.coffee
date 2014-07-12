angular.module('buildbot.common').directive 'rawdata',
['RecursionHelper', (RecursionHelper) ->
    replace: true
    restrict: 'E'
    scope: {data:'='}
    templateUrl: 'views/rawdata.html'
    compile: RecursionHelper.compile
    controller: [ '$scope', ($scope) ->
        $scope.isObject = (v) -> _.isObject(v) and not _.isArray(v)
        $scope.isArrayOfObjects = (v) -> _.isArray(v) and v.length > 0 and _.isObject(v[0])
    ]
]