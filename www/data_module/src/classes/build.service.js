class Build {
    constructor(Base, dataService) {
        let BuildInstance;
        return (BuildInstance = class BuildInstance extends Base {
            constructor(object, endpoint) {
                const endpoints = [
                    'changes',           // /changes
                    'properties',        // /properties
                    'steps'             // /steps/:name
                                        // /steps/:stepid
                ];

                super(object, endpoint, endpoints);
            }
        });
    }
}


angular.module('bbData')
.factory('Build', ['Base', 'dataService', Build]);
