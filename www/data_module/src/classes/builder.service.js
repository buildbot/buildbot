class Builder {
    constructor(Base, dataService) {
        let BuilderInstance;
        return (BuilderInstance = class BuilderInstance extends Base {
            constructor(object, endpoint) {
                const endpoints = [
                    'builds',            // /builds/:buildid
                    'buildrequests',     // /buildrequests/:buildrequestid
                    'forceschedulers',   // /forceschedulers
                    'workers',           // /workers/:workerid
                                        // /workers/:name
                    'masters'           // /masters/:masterid
                ];

                super(object, endpoint, endpoints);
            }
        });
    }
}


angular.module('bbData')
.factory('Builder', ['Base', 'dataService', Builder]);
