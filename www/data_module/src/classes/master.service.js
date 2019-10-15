class Master {
    constructor(Base, dataService) {
        let MasterInstance;
        return (MasterInstance = class MasterInstance extends Base {
            constructor(object, endpoint) {
                const endpoints = [
                    'builders',          // /builders/:builderid
                    'workers',           // /workers/:workerid
                                        // /workers/:name
                    'changesources',     // /changesources/:changesourceid
                    'schedulers'        // /schedulers/:schedulerid
                ];

                super(object, endpoint, endpoints);
            }
        });
    }
}


angular.module('bbData')
.factory('Master', ['Base', 'dataService', Master]);
