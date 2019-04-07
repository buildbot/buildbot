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


angular.module('app')
.factory('Worker', ['Base', 'dataService', Worker]);