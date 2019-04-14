class Changelist
    constructor: ->
        return {
            replace: true
            restrict: 'E'
            scope: {changes: '=?'}
            templateUrl: 'views/changelist.html'
            controller: '_changeListController'
        }

class _changeList
    constructor: ($scope, dataUtilsService) ->

        $scope.expandDetails = ->
            for change in $scope.changes
                change.show_details = true

        $scope.collapseDetails = ->
            for change in $scope.changes
                change.show_details = false


angular.module('common')
.directive('changelist', [Changelist])
.controller('_changeListController', ['$scope', 'dataUtilsService', _changeList])