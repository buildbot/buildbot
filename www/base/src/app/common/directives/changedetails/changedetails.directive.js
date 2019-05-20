class Changedetails {
    constructor() {
        return {
            replace: true,
            restrict: 'E',
            scope: {
                change: '=',
                compact: '=?'
            },
            template: require('./changedetails.tpl.jade'),
        };
    }
}


angular.module('common')
.directive('changedetails', [Changedetails]);
