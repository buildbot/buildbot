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

            if i == "edit"
                glMenuServiceProvider.addGroup
                    name: group.name
            else
                groupForProvider =
                    name: group.name
                    caption: _.capitalize(group.name)
                    icon: group.name
                    order: if i == "edit" then undefined else group.name.length
                glMenuServiceProvider.addGroup groupForProvider
                if i == "cab"
                    glMenuServiceProvider.setDefaultGroup groupForProvider


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
                        group: if item.name == "banedit" then undefined else group.name
                        caption: if item.name == "editedit" then undefined else _.capitalize(item.name)
                $stateProvider.state(state)
        null

    it 'should generate the menu correctly', inject (glMenuService) ->
        groups = glMenuService.getGroups()
        namedGroups = {}
        for g in groups
            namedGroups[g.name] = g
        expect(groups.length).toEqual(7)
        expect(groups[0].items.length).toEqual(7)
        expect(namedGroups['bug'].items.length).toEqual(0)
        expect(namedGroups['bug'].caption).toEqual('Bugcab')

    it 'should have the default group set', inject (glMenuService) ->
        defaultGroup = glMenuService.getDefaultGroup()
        groups = glMenuService.getGroups()
        expect(defaultGroup).toEqual(groups[0])

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

    # simple test to make sure the directive loads
    it 'should remove empty groups', ->

        # configure the menu a little bit more.. with an erronous state
        module (glMenuServiceProvider) ->
            glMenuServiceProvider.addGroup
                name: "foo"
            null

        inject (glMenuService) ->
            groups = glMenuService.getGroups()
            namedGroups = {}
            for g in groups
                namedGroups[g.name] = g
            expect(namedGroups["foo"]).not.toBeDefined()
