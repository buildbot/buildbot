unless __karma__?
    window.describe = ->

# define sample application logic

m = angular.module("app", ["guanlecoja.ui"]);

m.config ($stateProvider, glMenuServiceProvider) ->

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
            glMenuServiceProvider.group
                name: group.name
                caption: _.string.humanize(group.name)
                icon: group.name
                order: group.name.length

        for group in groups
            for item in group.items
                state =
                    controller: "dummyController"
                    template: "<h1>{{stateName}}</h1>"
                    name: item.name
                    url: '/' + item.name
                    data:
                        group: group.name
                        caption: _.string.humanize(item.name)
                $stateProvider.state(state)

m.controller "dummyController", ($scope, $state) ->
    $scope.stateName = $state.current.name
