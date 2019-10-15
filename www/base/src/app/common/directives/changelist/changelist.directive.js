/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Changelist {
    constructor() {
        return {
            replace: true,
            restrict: 'E',
            scope: {changes: '=?'},
            template: require('./changelist.tpl.jade'),
            controller: '_changeListController'
        };
    }
}

class _changeList {
    constructor($scope, dataUtilsService) {

        $scope.expandDetails = () =>
            Array.from($scope.changes).map((change) =>
                (change.show_details = true))
        ;

        $scope.collapseDetails = () =>
            Array.from($scope.changes).map((change) =>
                (change.show_details = false))
        ;
    }
}


angular.module('common')
.directive('changelist', [Changelist])
.controller('_changeListController', ['$scope', 'dataUtilsService', _changeList]);
