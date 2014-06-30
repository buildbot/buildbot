angular.module('buildbot.console_view').directive 'buildersHeader',
    [ ->
        replace: true
        restrict: 'EA' # E: Element, A: Attribute
        scope: {
            width: '='
            builders: '='
            bigHeader: '='
        }
        templateUrl: 'console_view/views/buildersheader.html'
        controller: ['$scope', class
            constructor: ($scope) ->
                @bigHeader = true

                $scope.$watch 'width', (@width) =>
                $scope.$watchCollection 'builders', (@builders) =>
                $scope.$watch 'bigHeader', (@bigHeader) =>
        ]
        controllerAs: 'bh'
    ]