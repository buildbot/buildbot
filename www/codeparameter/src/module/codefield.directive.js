
// defines custom field directives which only have templates
class Codefield {
    constructor() {
        return {
            replace: false,
            restrict: 'E',
            scope: false,
            template: require('./codefield.tpl.jade')
        };
    }
}

angular.module('codeparameter')
.directive('codefield', [Codefield]);
