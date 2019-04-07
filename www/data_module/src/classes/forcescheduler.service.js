class Forcescheduler {
    constructor(Base, dataService) {
        let ForceschedulerInstance;
        return (ForceschedulerInstance = class ForceschedulerInstance extends Base {
            constructor(object, endpoint) {
                super(object, endpoint);
            }
        });
    }
}


angular.module('app')
.factory('Forcescheduler', ['Base', 'dataService', Forcescheduler]);