class Rawdata {
    constructor(RecursionHelper) {
        return {
            replace: true,
            restrict: 'E',
            scope: {data:'='},
            template: require('./rawdata.tpl.jade'),
            compile: RecursionHelper.compile,
            controller: '_rawdataController'
        };
    }
}

class _rawdata {
    constructor($scope) {
        $scope.isObject = v => _.isObject(v) && !_.isArray(v);
        $scope.isArrayOfObjects = v => _.isArray(v) && (v.length > 0) && _.isObject(v[0]);
    }
}

angular.module('common')
.directive('rawdata', ['RecursionHelper', Rawdata])
.controller('_rawdataController', ['$scope', _rawdata]);
