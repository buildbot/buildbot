/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS206: Consider reworking classes to avoid initClass
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class GlMenu {
    static initClass() {

        this.prototype.appTitle = "set AppTitle using GlMenuServiceProvider.setAppTitle";

        this.prototype.$get = ["$state", function($state) {
            let group;
            for (let state of Array.from($state.get().slice(1))) {
                ({ group } = state.data);
                if (group == null) {
                    continue;
                }

                if (!this.groups.hasOwnProperty(group)) {
                    throw Error(`group ${group} has not been defined with glMenuProvider.group(). has: ${_.keys(this.groups)}`);
                }

                this.groups[group].items.push({
                    caption: state.data.caption || _.capitalize(state.name),
                    sref: state.name
                });
            }

            for (let name in this.groups) {
                // if a group has only no item, we juste delete it
                group = this.groups[name];
                if ((group.items.length === 0) && !group.separator) {
                    delete this.groups[name];
                // if a group has only one item, then we put the group == the item
                } else if (group.items.length === 1) {
                    const item = group.items[0];
                    group.caption = item.caption;
                    group.sref = item.sref;
                    group.items = [];
                } else {
                    group.sref = ".";
                }
            }
            const groups = _.values(this.groups);
            groups.sort((a,b) => a.order - b.order);
            const self = this;
            return {
                getGroups() { return groups; },
                getDefaultGroup() { return self.defaultGroup; },
                getFooter() { return self.footer; },
                getAppTitle() { return self.appTitle; }
            };
        }
        ];
    }
    constructor() {
        this.groups = {};
        this.defaultGroup = null;
        this.footer = [];
    }

    addGroup(group) {
        group.items = [];
        if (group.order == null) { group.order = 99; }
        this.groups[group.name] = group;
        return this.groups;
    }

    setDefaultGroup(group) {
        return this.defaultGroup = group;
    }

    setFooter(footer) {
        return this.footer = footer;
    }

    setAppTitle(title) {
        return this.appTitle = title;
    }
}
GlMenu.initClass();


angular.module('guanlecoja.ui')
.provider('glMenuService', [GlMenu]);
