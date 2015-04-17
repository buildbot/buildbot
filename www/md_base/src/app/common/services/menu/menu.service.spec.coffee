beforeEach module 'app'

describe 'menuService', ->
    _menuServiceProvider = null

    beforeEach module (menuServiceProvider) ->
        _menuServiceProvider = menuServiceProvider
        return null

    it 'should work well', inject (menuService) ->
        _menuServiceProvider.items = []
        expect(menuService.getItems().length).toBe(0)

        item1 =
            name: 'testitem1'
            caption: 'Test Item 1'
            icon: 'testicon'
            order: 0

        # add an item
        _menuServiceProvider.addItem item1

        expect(menuService.getItems().length).toBe(1)
        expect(menuService.getItems()[0]).toBe(item1)

        # should add an order of 99 if that parameter is missing
        item2 =
            name: 'testitem2'
            caption: 'Test Item 2'
            icon: 'testicon'

        _menuServiceProvider.addItem item2

        expect(menuService.getItems().length).toBe(2)
        expect(menuService.getItems()[1]).toBe(item2)
        expect(menuService.getItems()[1].order).toBe(99)

        # test current propery
        _menuServiceProvider.current = 'testitem1'
        expect(menuService.getCurrent()).toBe('testitem1')
        _menuServiceProvider.current = 'testitem2'
        expect(menuService.getCurrent()).toBe('testitem2')

