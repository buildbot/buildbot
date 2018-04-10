class GlMenu extends Provider
    constructor: ->
        @groups = {}
        @defaultGroup = null
        @footer = []

    appTitle: "set AppTitle using GlMenuServiceProvider.setAppTitle"

    addGroup: (group) ->
        group.items = []
        group.order ?= 99
        @groups[group.name] = group
        return @groups

    setDefaultGroup: (group) ->
        @defaultGroup = group

    setFooter: (footer) ->
        @footer = footer

    setAppTitle: (title) ->
        @appTitle = title

    $get: ["$state", ($state) ->
        for state in $state.get()[1...]
            group = state.data.group
            unless group?
                continue

            unless @groups.hasOwnProperty(group)
                throw Error("group #{group} has not been defined with glMenuProvider.group(). has: #{_.keys(@groups)}")

            @groups[group].items.push
                caption: state.data.caption || _.capitalize(state.name)
                sref: state.name

        for name, group of @groups
            # if a group has only no item, we juste delete it
            if group.items.length == 0 and not group.separator
                delete @groups[name]
            # if a group has only one item, then we put the group == the item
            else if group.items.length == 1
                item = group.items[0]
                group.caption = item.caption
                group.sref = item.sref
                group.items = []
            else
                group.sref = "."
        groups = _.values(@groups)
        groups.sort((a,b) -> a.order - b.order)
        self = @
        return {
            getGroups: -> groups
            getDefaultGroup: -> self.defaultGroup
            getFooter: -> self.footer
            getAppTitle: -> self.appTitle
        }
    ]
