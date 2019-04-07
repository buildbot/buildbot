class Api {
    constructor() { return 'api/v2/'; }
}

class Endpoints {
    constructor() {
        // Rootlinks
        return [
            'builders',
            'builds',
            'buildrequests',
            'workers',
            'buildsets',
            'changes',
            'changesources',
            'masters',
            'sourcestamps',
            'schedulers',
            'forceschedulers'
        ];
    }
}


angular.module('app')
.constant('API', Api())
.constant('ENDPOINTS', Endpoints());