class Rawdata
    constructor: (RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {data:'='}
            templateUrl: 'views/rawdata.html'
            compile: RecursionHelper.compile
            controller: '_rawdataController'
        }

class _rawdata
    constructor: ($scope) ->
        $scope.isObject = (v) -> _.isObject(v) and not _.isArray(v)
        $scope.isArrayOfObjects = (v) -> _.isArray(v) and v.length > 0 and _.isObject(v[0])

angular.module('common')
.directive('rawdata', ['RecursionHelper', Rawdata])
.controller('_rawdataController', ['$scope', _rawdata])