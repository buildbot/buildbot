class Properties {
    constructor() {
        return {
            replace: true,
            restrict: 'E',
            scope: {properties: '='},
            template: require('./properties.tpl.jade'),
            controller: '_propertiesController',
        };
    }
}

function _properties($scope) {
    $scope.copy = function(value) {
        value = JSON.stringify(value);

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(value);
        } else {
            var element = document.createElement('textarea');
            element.style = 'position:absolute; width:1px; height:1px; top:-10000px; left:-10000px';
            element.value = value;
            document.body.appendChild(element);
            element.select();
            document.execCommand('copy');
            document.body.removeChild(element);
        }
    }
}


angular.module('common')
.directive('properties', [Properties])
.controller('_propertiesController', ['$scope', _properties]);
