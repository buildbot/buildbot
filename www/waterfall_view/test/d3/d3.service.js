// fake d3service for tests.
// d3Service is supposed to be provided by the main www/base app
// and is loading d3 asynchronously on demand

import * as d3 from 'd3';

class D3 {
    constructor($q) {
        const d = $q.defer();

        // Resolve function
        d.resolve(d3);

        return {get() { return d.promise; }};
    }
}

angular.module('bbData')
.service('d3Service', ['$q', D3]);
