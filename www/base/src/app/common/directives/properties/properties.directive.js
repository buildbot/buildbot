class Properties {
    constructor() {
        return {
            replace: true,
            restrict: 'E',
            scope: {properties: '='},
            template: require('./properties.tpl.jade'),
        };
    }
}


angular.module('common')
.directive('properties', [Properties]);
