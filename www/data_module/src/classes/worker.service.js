class Worker {
    constructor(Base, dataService) {
        let WorkerInstance;
        return (WorkerInstance = class WorkerInstance extends Base {
            constructor(object, endpoint) {
                super(object, endpoint);
            }
        });
    }
}


angular.module('bbData')
.factory('Worker', ['Base', 'dataService', Worker]);
