/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
// Load d3 script via jquery
// We load those 50kB+ only when needed by plugins
// actually, this is loaded when someone is requiring DI of this service
class D3 {
    constructor($document, $q, config, $rootScope) {
        const d = $q.defer();

        // Resolve function
        $.getScript('d3.min.js', () =>
            $rootScope.$apply(() => d.resolve(window.d3))
        );

        return {get() { return d.promise; }};
    }
}


angular.module('app')
.service('d3Service', ['$document', '$q', 'config', '$rootScope', D3]);
