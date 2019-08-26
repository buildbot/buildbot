/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
// builder data used everywhere in the UI, so we implement a simple cache

// TODO this caching mechanism needs to be implemented eventually in data module
// Its much more complicated to do this generically, and keep the event mechanism,
// this is why we do this temporary workaround

// Objects returned by this service cannot use onNew/onUpdate mechanism of data module (as they are shared)

class buildersService {
    constructor($log, dataService) {
        // we use an always one dataService instance
        const data = dataService.open();
        const cache = {};
        /* make only one full list of builders. this is much faster than querying builders one by one*/
        data.getBuilders().onNew = builder => {
            let id = builder.builderid
            if (cache.hasOwnProperty(id)) {
                _.assign(cache[id], builder)
            } else {
                cache[id] = builder
            }
        }
        return {
            getBuilder(id) {
                if (cache.hasOwnProperty(id)) {
                    return cache[id]
                } else {
                    cache[id] = {}
                    return cache[id]
                }
            }
        };
    }
}


angular.module('common')
    .factory('buildersService', ['$log', 'dataService', buildersService]);
