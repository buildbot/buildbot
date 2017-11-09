# this function is meant to group builds into builders, but is written generically
# so that it can group any collection into another collection like a database join
class dataGrouperService extends Factory('common')
    constructor: ->
        return {
            groupBy: (collection1, collection2, joinid, attribute, joinlist) ->
                # @param collection1: collection holding the groups
                # @param collection2: collection that will be split into the collection1
                # @param joinid: the id that should be present in both collection items,
                #                and meant to match them
                # @param attribute: the collection1 item's attribute where to store collection2 groups
                # @param joinlist: optional attribute of collection2 items if the collection2
                #                  is pointing to several item of collection1
                temp_dict = {}
                onNew = collection1.onNew
                collection1.onNew = (item) ->
                    if temp_dict.hasOwnProperty(item[joinid])
                        item[attribute] = temp_dict[item[joinid]]
                    onNew(item)
                if joinlist?
                    collection2.onNew  = (item) ->
                        item[joinlist]?.forEach (item2) ->
                            # the collection1 might not be yet loaded, so we need to store the worker list
                            if collection1.hasOwnProperty(item2[joinid])
                                group = collection1.get(item2[joinid])[attribute] ?= []
                            else
                                group = temp_dict[item2[joinid]] ?= []
                            group.push(item)
                else
                    collection2.onNew = (item) ->
                        # the collection1 might not be yet loaded, so we need to store the worker list
                        if collection1.hasOwnProperty(item[joinid])
                            group = collection1.get(item[joinid])[attribute] ?= []
                        else
                            group = temp_dict[item[joinid]] ?= []
                        group.push(item)
        }
