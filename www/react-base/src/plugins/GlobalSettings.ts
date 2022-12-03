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
import {Config} from "../contexts/Config";

export type SettingValue = string | number | boolean;
export type SettingType = "string" | "integer" | "float" | "boolean";

export type SettingItemConfig = {
  name: string;
  type: SettingType;
  caption: string;
  defaultValue: SettingValue;
}

export type SettingGroupConfig = {
  name: string;
  caption: string;
  items: SettingItemConfig[];
}

export type SettingItem = {
  name: string;
  type: string;
  value: SettingValue;
  defaultValue: SettingValue;
  caption: string;
}

export type SettingGroup = {
  name: string;
  caption: string;
  items: {[name: string]: SettingItem};
}

export type SettingGroups = {[name: string]: SettingGroup};

type StoredSettingGroup = {[name: string]: SettingValue};
type StoredSettingGroups = {[name: string]: StoredSettingGroup};

export class GlobalSettings {
  @observable groups: SettingGroups = {};

  constructor() {
    makeObservable(this);
  }

  @action applyBuildbotConfig(config: Config) {
    if (config.ui_default_config !== undefined) {
      this.fillDefaults(config.ui_default_config);
    }
  }

  @action fillDefaults(uiConfig: {[key: string]: any}) {
    for (const [selector, value] of Object.entries(uiConfig)) {
      this.setSetting(selector, value);
    }
  }

  splitSelector(selector: string) {
    const groupAndSettingName = selector.split('.');
    if (groupAndSettingName.length !== 2) {
      console.error(`bad setting name ${selector}`);
      return null;
    }
    return groupAndSettingName;
  }

  getGroupBySelector(selector: string) {
    const groupAndSettingName = this.splitSelector(selector);
    if (groupAndSettingName === null) {
      return null;
    }
    const [groupName, settingName] = groupAndSettingName;
    if (!(groupName in this.groups)) {
      console.error(`bad setting name ${selector}: group does not exist`);
      return null;
    }
    return {
      group: this.groups[groupName],
      settingName: settingName
    }
  }

  @action load() {
    const settings = localStorage.getItem('settings');
    if (settings === null) {
      return;
    }
    try {
      const storedGroups = JSON.parse(settings) as StoredSettingGroups;
      for (const [groupName, storedGroup] of Object.entries(storedGroups)) {
        if (!(groupName in this.groups)) {
          console.log(`Ignoring unknown loaded setting group ${groupName}`);
          continue;
        }
        const group = this.groups[groupName];
        for (const [itemName, item] of Object.entries(storedGroup)) {
          if (!(itemName in group.items)) {
            console.log(`Ignoring unknown loaded setting ${groupName}.${itemName}`);
            continue;
          }
          this.setSettingItem(group.items[itemName], item);
        }
      }

    } catch (e) {
      console.error(`Got error ${e} when parsing settings`);
    }
  }

  save() {
    const storedGroups: StoredSettingGroups = {};
    for (const [groupName, group] of Object.entries(this.groups)) {
      const storedGroup: StoredSettingGroup = {};
      for (const [itemName, item] of Object.entries(group.items)) {
        storedGroup[itemName] = item.value;
      }
      storedGroups[groupName] = storedGroup;
    }
    localStorage.setItem('settings', JSON.stringify(storedGroups));
  }

  private getSettingItem(selector: string) {
    const groupAndSetting = this.getGroupBySelector(selector);
    if (groupAndSetting === null) {
      return null;
    }
    const {group, settingName} = groupAndSetting;
    if (!(settingName in group.items)) {
      console.error(`bad setting name ${selector}: setting does not exist`);
    }
    return group.items[settingName];
  }

  getSetting(selector: string) {
    return this.getSettingItem(selector)?.value;
  }

  private getTypedSettingOrDefault<T>(selector: string, type: string, def: T) {
    const item = this.getSettingItem(selector);
    if (item === null) {
      return def;
    }
    if (item.type !== type) {
      console.error(`Setting ${selector} has type ${item.type}, but expected ${type}`);
      return def;
    }
    return item.value as unknown as T;
  }

  getIntegerSetting(selector: string) {
    return this.getTypedSettingOrDefault(selector, 'integer', 0);
  }

  getFloatSetting(selector: string) {
    return this.getTypedSettingOrDefault(selector, 'float', 0);
  }

  getStringSetting(selector: string) {
    return this.getTypedSettingOrDefault(selector, 'string', '');
  }

  getBooleanSetting(selector: string) {
    return this.getTypedSettingOrDefault(selector, 'boolean', false);
  }

  @action private setSettingItem(item: SettingItem, value: SettingValue) {
    switch (item.type) {
      case "string":
        item.value = value.toString();
        break;
      case "integer": {
        const newValue = Number.parseInt(value.toString());
        if (!isNaN(newValue)) {
          item.value = newValue;
        } else {
          console.error(`Invalid integer setting value ${value}`);
        }
        break;
      }
      case "float": {
        const newValue = Number.parseFloat(value.toString());
        if (!isNaN(newValue)) {
          item.value = newValue;
        } else {
          console.error(`Invalid float setting value ${value}`);
        }
        break;
      }
      case "boolean":
        if (value.toString() === "true") {
          item.value = true;
        } else if (value.toString() === "false") {
          item.value = false;
        } else {
          console.error(`Invalid bool setting value ${value}`);
        }
        break;
    }
  }

  @action setSetting(selector: string, value: SettingValue) {
    const item = this.getSettingItem(selector);
    if (item === null) {
      return;
    }
    this.setSettingItem(item, value);
  }

  /** Adds a new setting group and its setting items.

      Items of a single group may be added via multiple calls to this function. If group caption
      is different between the calls, it is unspecified which value will be used.

      This function may only be called during import time. New options should not be added once
      the app is running.
  */
  @action addGroup(config: SettingGroupConfig) {
    if (config.name === null) {
      throw Error(`Group (with caption : ${config.caption}) must have a correct name property.`);
    }

    if (config.name in this.groups) {
      const group = this.groups[config.name];
      for (const item of config.items) {
        if (item.name in group.items) {
          console.error(`Duplicate group item ${config.name}.${item.name}`);
          continue;
        }
        group.items[item.name] = {
          name: item.name,
          type: item.type,
          value: item.defaultValue,
          defaultValue: item.defaultValue,
          caption: item.caption,
        };
      }
      return;
    }

    const items: {[name: string]: SettingItem} = {};
    for (const item of config.items) {
      items[item.name] = {
        name: item.name,
        type: item.type,
        value: item.defaultValue,
        defaultValue: item.defaultValue,
        caption: item.caption,
      };
    }
    this.groups[config.name] = {
      name: config.name,
      caption: config.caption,
      items: items,
    };
  }
};

export const globalSettings = new GlobalSettings();
