angular.module('buildbot.console_view').directive 'buildersHeader',
    [ ->
        replace: true
        restrict: 'EA' # E: Element, A: Attribute
        scope: {
            width: '='
            cellWidth: '='
            builders: '='
        }
        templateUrl: 'buildbot.console_view/views/buildersheader.html'
        controller: ['$scope', class
            constructor: ($scope) ->
                $scope.$watch 'width', (@width) =>
                $scope.$watch 'cellWidth', (@cellWidth) =>
                $scope.$watchCollection 'builders', (@builders) =>
        ]
        controllerAs: 'bh'
    ]
