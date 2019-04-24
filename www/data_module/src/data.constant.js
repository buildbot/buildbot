class Api {
    constructor() { return new String('api/v2/'); }
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


angular.module('bbData')
.constant('API', new Api())
.constant('ENDPOINTS', new Endpoints());
