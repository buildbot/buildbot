class Scheduler {
    constructor(Base, dataService) {
        let SchedulerInstance;
        return (SchedulerInstance = class SchedulerInstance extends Base {
            constructor(object, endpoint) {
                super(object, endpoint);
            }
        });
    }
}


angular.module('app')
.factory('Scheduler', ['Base', 'dataService', Scheduler]);