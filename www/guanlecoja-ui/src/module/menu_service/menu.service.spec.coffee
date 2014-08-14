describe 'menuService', ->
    beforeEach module "guanlecoja.ui", ($stateProvider, glMenuServiceProvider) ->
        _glMenuServiceProvider = glMenuServiceProvider
        stateProvider = $stateProvider
        groups = []
        for i in ["cab", "camera", "bug", "calendar", "ban", "archive", "edit"]
            group =
                name: i
                items: []
            for j in ["cab", "camera", "bug", "calendar", "ban", "archive", "edit"]
                group.items.push
                    name: i + j
                if i == "bug"
                    break
            groups.push group
            glMenuServiceProvider.addGroup
                name: group.name
                caption: _.string.humanize(group.name)
                icon: group.name
                order: group.name.length

        glMenuServiceProvider.setFooter [
            caption: "Github"
            href: "https://github.com/tardyp/guanlecoja-ui"
        ]
        glMenuServiceProvider.setAppTitle("Guanlecoja-UI")
        for group in groups
            for item in group.items
                state =
                    name: item.name
                    url: '/' + item.name
                    data:
                        group: group.name
                        caption: _.string.humanize(item.name)
                $stateProvider.state(state)
        null

    # simple test to make sure the directive loads
    it 'should generate the menu correctly', inject (glMenuService) ->
        groups = glMenuService.getGroups()
        namedGroups = {}
        for g in groups
            namedGroups[g.name] = g
        expect(groups.length).toEqual(7)
        expect(groups[0].items.length).toEqual(7)
        expect(namedGroups['bug'].items.length).toEqual(0)
        expect(namedGroups['bug'].caption).toEqual('Bugcab')

    # simple test to make sure the directive loads
    it 'should generate error if group is undefined', ->

        # configure the menu a little bit more.. with an erronous state
        module ($stateProvider, glMenuServiceProvider) ->
            $stateProvider.state
                name: "foo"
                data:
                    group: "bar"  # not existing group!
            null
        run = ->
            inject (glMenuService) ->
                groups = glMenuService.getGroups()
        expect(run).toThrow()
