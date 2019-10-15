class Changesource {
    constructor(dataService, Base) {
        let ChangesourceInstance;
        return (ChangesourceInstance = class ChangesourceInstance extends Base {
            constructor(object, endpoint) {
                super(object, endpoint);
            }
        });
    }
}


angular.module('bbData')
.factory('Changesource', ['dataService', 'Base', Changesource]);
