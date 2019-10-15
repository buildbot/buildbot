/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('menuService', function() {
    beforeEach(angular.mock.module("guanlecoja.ui", function($stateProvider, glMenuServiceProvider) {
        let group;
        const _glMenuServiceProvider = glMenuServiceProvider;
        const stateProvider = $stateProvider;
        const groups = [];
        for (let i of ["cab", "camera", "bug", "calendar", "ban", "archive", "edit"]) {
            group = {
                name: i,
                items: []
            };
            for (let j of ["cab", "camera", "bug", "calendar", "ban", "archive", "edit"]) {
                group.items.push({
                    name: i + j});
                if (i === "bug") {
                    break;
                }
            }
            groups.push(group);

            if (i === "edit") {
                glMenuServiceProvider.addGroup({
                    name: group.name});
            } else {
                const groupForProvider = {
                    name: group.name,
                    caption: _.capitalize(group.name),
                    icon: group.name,
                    order: i === "edit" ? undefined : group.name.length
                };
                glMenuServiceProvider.addGroup(groupForProvider);
                if (i === "cab") {
                    glMenuServiceProvider.setDefaultGroup(groupForProvider);
                }
            }
        }


        glMenuServiceProvider.setFooter([{
            caption: "Github",
            href: "https://github.com/tardyp/guanlecoja-ui"
        }
        ]);
        glMenuServiceProvider.setAppTitle("Guanlecoja-UI");
        for (group of Array.from(groups)) {
            for (let item of Array.from(group.items)) {
                const state = {
                    name: item.name,
                    url: `/${item.name}`,
                    data: {
                        group: item.name === "banedit" ? undefined : group.name,
                        caption: item.name === "editedit" ? undefined : _.capitalize(item.name)
                    }
                };
                $stateProvider.state(state);
            }
        }
        return null;
    })
    );

    it('should generate the menu correctly', inject(function(glMenuService) {
        const groups = glMenuService.getGroups();
        const namedGroups = {};
        for (let g of Array.from(groups)) {
            namedGroups[g.name] = g;
        }
        expect(groups.length).toEqual(7);
        expect(groups[0].items.length).toEqual(7);
        expect(namedGroups['bug'].items.length).toEqual(0);
        expect(namedGroups['bug'].caption).toEqual('Bugcab');
    })
    );

    it('should have the default group set', inject(function(glMenuService) {
        const defaultGroup = glMenuService.getDefaultGroup();
        const groups = glMenuService.getGroups();
        expect(defaultGroup).toEqual(groups[0]);
    })
    );

    // simple test to make sure the directive loads
    it('should generate error if group is undefined', function() {

        // configure the menu a little bit more.. with an erronous state
        angular.mock.module(function($stateProvider, glMenuServiceProvider) {
            $stateProvider.state({
                name: "foo",
                data: {
                    group: "bar"
                }
            });  // not existing group!
            return null;
        });
        const run = () =>
            inject(function(glMenuService) {
                let groups;
                return groups = glMenuService.getGroups();
            })
        ;
        expect(run).toThrow();
    });

    // simple test to make sure the directive loads
    it('should remove empty groups', function() {

        // configure the menu a little bit more.. with an erronous state
        angular.mock.module(function(glMenuServiceProvider) {
            glMenuServiceProvider.addGroup({
                name: "foo"});
            return null;
        });

        inject(function(glMenuService) {
            const groups = glMenuService.getGroups();
            const namedGroups = {};
            for (let g of Array.from(groups)) {
                namedGroups[g.name] = g;
            }
            expect(namedGroups["foo"]).not.toBeDefined();
        });
    });
});
