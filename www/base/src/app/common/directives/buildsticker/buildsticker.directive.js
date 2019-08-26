/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */

import moment from 'moment';

class Buildsticker {
    constructor(RecursionHelper) {
        return {
            replace: true,
            restrict: 'E',
            scope: {build: '=?', builder: '=?', buildid: '=?'},
            template: require('./buildsticker.tpl.jade'),
            controller: '_buildstickerController'
        };
    }
}
class _buildsticker {
    constructor($scope, dataService, buildersService, resultsService, $urlMatcherFactory, $location) {
        $scope.$watch((() => moment().unix()), () => $scope.now = moment().unix());

        // make resultsService utilities available in the template
        _.mixin($scope, resultsService);

        const data = dataService.open().closeOnDestroy($scope);
        $scope.$watch("buildid", function(buildid) {
            if ((buildid == null)) { return; }
            data.getBuilds(buildid).onNew = build => $scope.build = build;
        });

        $scope.$watch('build', function(build) {
            if (!$scope.builder && ((build != null ? build.builderid : undefined) != null)) {
                $scope.builder = buildersService.getBuilder(build.builderid);
            }
        });
    }
}


angular.module('common')
.directive('buildsticker', ['RecursionHelper', Buildsticker])
.controller('_buildstickerController', ['$scope', 'dataService', 'buildersService', 'resultsService', '$urlMatcherFactory', '$location', _buildsticker]);
