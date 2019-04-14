class BuildsTable
    constructor: (RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {builds: '=?', builder: '=?', builders: '=?'}
            templateUrl: 'views/buildstable.html'
            controller: '_buildstableController'
        }
class _buildstable
    constructor: ($scope, resultsService) ->
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)
        return


angular.module('common')
.directive('buildsTable', ['RecursionHelper', BuildsTable])
.controller('_buildstableController', ['$scope', 'resultsService', _buildstable])