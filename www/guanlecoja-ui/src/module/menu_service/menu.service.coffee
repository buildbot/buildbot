class GlMenu extends Provider
    constructor: ->
        @groups = {}

        @group = (group) ->
            @groups[group.name] = group
            return @groups

        @$get = ($state) ->
            groups = {}
            for state in $state.get()[1...]
                group = state.data.group
                unless groups.hasOwnProperty(group)
                    groups[group] =
                        caption: group
                        sref: group
                        icon: group
                        items: []
                groups[group].items.push
                    caption: state.name
                    sref: state.name
            groups = _.values(groups)
            return {
                getGroups: -> groups
            }
