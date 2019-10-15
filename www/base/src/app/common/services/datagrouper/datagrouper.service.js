/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS104: Avoid inline assignments
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
// this function is meant to group builds into builders, but is written generically
// so that it can group any collection into another collection like a database join
class dataGrouperService {
    constructor() {
        return {
            groupBy(collection1, collection2, joinid, attribute, joinlist) {
                // @param collection1: collection holding the groups
                // @param collection2: collection that will be split into the collection1
                // @param joinid: the id that should be present in both collection items,
                //                and meant to match them
                // @param attribute: the collection1 item's attribute where to store collection2 groups
                // @param joinlist: optional attribute of collection2 items if the collection2
                //                  is pointing to several item of collection1
                const temp_dict = {};
                const { onNew } = collection1;
                collection1.onNew = function(item) {
                    if (temp_dict.hasOwnProperty(item[joinid])) {
                        item[attribute] = temp_dict[item[joinid]];
                    }
                    onNew(item);
                };
                if (joinlist != null) {
                    collection2.onNew = item =>
                        item[joinlist] != null ? item[joinlist].forEach(function(item2) {
                            // the collection1 might not be yet loaded, so we need to store the worker list
                            let group;
                            if (collection1.hasOwnProperty(item2[joinid])) {
                                let base;
                                group = (base = collection1.get(item2[joinid]))[attribute] != null ? base[attribute] : (base[attribute] = []);
                            } else {
                                group = temp_dict[item2[joinid]] != null ? temp_dict[item2[joinid]] : (temp_dict[item2[joinid]] = []);
                            }
                            if (!Array.from(group).includes(item)) {
                                group.push(item);
                            }
                        }) : undefined
                    ;
                } else {
                    collection2.onNew = function(item) {
                        // the collection1 might not be yet loaded, so we need to store the worker list
                        let group;
                        if (collection1.hasOwnProperty(item[joinid])) {
                            let base;
                            group = (base = collection1.get(item[joinid]))[attribute] != null ? base[attribute] : (base[attribute] = []);
                        } else {
                            group = temp_dict[item[joinid]] != null ? temp_dict[item[joinid]] : (temp_dict[item[joinid]] = []);
                        }
                        group.push(item);
                    };
                }
            }
        };
    }
}


angular.module('common')
.factory('dataGrouperService', [dataGrouperService]);
