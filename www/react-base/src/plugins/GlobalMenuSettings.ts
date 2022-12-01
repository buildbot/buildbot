/*
  This file is part of Buildbot.  Buildbot is free software: you can
  redistribute it and/or modify it under the terms of the GNU General Public
  License as published by the Free Software Foundation, version 2.

  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
  details.

  You should have received a copy of the GNU General Public License along with
  this program; if not, write to the Free Software Foundation, Inc., 51
  Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

  Copyright Buildbot Team Members
*/

import {action, makeObservable, observable} from "mobx";

export type GroupSettings = {
  name: string;
  parentName: string | null;
  caption: string;
  route: string | null;
  icon: string | null;
  order: number | null;
};

export type ResolvedGroupSettings = {
  name: string;
  caption: string;
  route: string | null;
  icon: string | null;
  order: number;
  subGroups: ResolvedGroupSettings[];
};

export type FooterItemSettings = {
  caption: string;
  route: string;
};

export class GlobalMenuSettings {
  @observable groups: ResolvedGroupSettings[] = [];
  @observable footerItems: FooterItemSettings[] = [];
  @observable appTitle: string = 'Buildbot';

  constructor() {
    makeObservable(this);
  }

  // Inserts the given group. If settings.parentName is null, the group is inserted to the list
  // of top-level groups. Otherwise it is inserted as a subgroup of the group named
  // settings.parentName, which must already exist.
  @action addGroup(settings: GroupSettings) {
    const insertSettings: ResolvedGroupSettings = {
      name: settings.name,
      caption: settings.caption,
      route: settings.route,
      icon: settings.icon,
      order: settings.order === null ? 99 : settings.order,
      subGroups: []
    }

    const listToAdd = this.findParentGroupList(settings.parentName);

    this.removeDuplicateSettings(listToAdd, settings);

    let insertIndex = listToAdd.findIndex(s => s.order > insertSettings.order);
    insertIndex = insertIndex === -1 ? listToAdd.length : insertIndex;
    listToAdd.splice(insertIndex, 0, insertSettings);
  }

  private removeDuplicateSettings(currSettings: ResolvedGroupSettings[], settings: GroupSettings) {
    const itemsToRemove: number[] = [];
    currSettings.forEach((currSettings, i) => {
      if (currSettings.name === settings.name && currSettings.route === settings.route) {
        itemsToRemove.push(i);
      }
    });
    for (const i of itemsToRemove.reverse()) {
      currSettings.splice(i, 1);
    }
  }

  private findParentGroupList(parentName: string | null) {
    if (parentName === null) {
      return this.groups;
    }
    const group = this.findNamedGroupInListRecurse(this.groups, parentName);
    if (group === null) {
      throw new Error(`Could not find named group ${parentName}`)
    }
    return group.subGroups;
  }

  private findNamedGroupInListRecurse(groups: ResolvedGroupSettings[],
                                      name: string): ResolvedGroupSettings | null {
    for (const group of groups) {
      if (group.name === name) {
        return group;
      }
      const foundSubGroup = this.findNamedGroupInListRecurse(group.subGroups, name);
      if (foundSubGroup !== null) {
        return foundSubGroup;
      }
    }
    return null;
  }

  @action setAppTitle(title: string) {
    this.appTitle = title;
  }

  @action setFooter(items: FooterItemSettings[]) {
    this.footerItems = items;
  }
};

export const globalMenuSettings = new GlobalMenuSettings();
