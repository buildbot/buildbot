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
import {Config} from "buildbot-ui";
import {ISettings, registerBuildbotSettingsSingleton} from "buildbot-plugin-support";

export type SettingValue = string | number | boolean;
export type SettingType = "string" | "integer" | "float" | "boolean" | "choice_combo";

export type SettingItemConfig = {
  name: string;
  type: SettingType;
  caption: string;
  defaultValue: SettingValue;
  choices?: string[]; // only when type == "choice_combo"
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
  valueIsSet: boolean;
  defaultValue: SettingValue;
  choices?: string[]; // only when type == "choice_combo"
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

export class GlobalSettings implements ISettings {
  @observable groups: SettingGroups = {};

  constructor() {
    makeObservable(this);
  }

  @action applyBuildbotConfig(config: Config, filterGroup?: string) {
    if (config.ui_default_config !== undefined) {
      this.fillDefaults(config.ui_default_config, filterGroup);
    }
  }

  @action fillDefaults(uiConfig: {[key: string]: any}, filterGroup?: string) {
    for (const [selector, value] of Object.entries(uiConfig)) {
      if (filterGroup !== undefined) {
        const groupAndSetting = this.splitSelector(selector);
        if (groupAndSetting === null || groupAndSetting[0] != filterGroup)
          continue;
      }
      this.setSettingDefaultValue(selector, value);
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

  @action load(filterGroup?: string) {
    const settings = localStorage.getItem('settings');
    if (settings === null) {
      return;
    }
    try {
      const storedGroups = JSON.parse(settings) as StoredSettingGroups;
      for (const [groupName, storedGroup] of Object.entries(storedGroups)) {
        if (filterGroup !== undefined && groupName != filterGroup)
           continue;
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
          this.setSettingItem(group.items[itemName], item, true);
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
        if (item.valueIsSet) {
          storedGroup[itemName] = item.value;
        }
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

  getChoiceComboSetting(selector: string) {
    return this.getTypedSettingOrDefault(selector, 'choice_combo', '');
  }

  @action private setSettingItemNoCheck(item: SettingItem, value: SettingValue, setValueIsSet: boolean) {
    item.value = value;
    if (setValueIsSet) {
      item.valueIsSet = true;
    }
  }

  private setSettingItem(item: SettingItem, value: SettingValue, setValueIsSet: boolean) {
    switch (item.type) {
      case "string":
      case "choice_combo":
        this.setSettingItemNoCheck(item, value.toString(), setValueIsSet);
        break;
      case "integer": {
        const newValue = Number.parseInt(value.toString());
        if (!isNaN(newValue)) {
          this.setSettingItemNoCheck(item, newValue, setValueIsSet);
        } else {
          console.error(`Invalid integer setting value ${value}`);
        }
        break;
      }
      case "float": {
        const newValue = Number.parseFloat(value.toString());
        if (!isNaN(newValue)) {
          this.setSettingItemNoCheck(item, newValue, setValueIsSet);
        } else {
          console.error(`Invalid float setting value ${value}`);
        }
        break;
      }
      case "boolean":
        if (value.toString() === "true") {
          this.setSettingItemNoCheck(item, true, setValueIsSet);
        } else if (value.toString() === "false") {
          this.setSettingItemNoCheck(item, false, setValueIsSet);
        } else {
          console.error(`Invalid bool setting value ${value}`);
        }
        break;
    }
  }

  @action setSettingImpl(selector: string, value: SettingValue, setValueIsSet: boolean) {
    const item = this.getSettingItem(selector);
    if (item === null) {
      return;
    }
    this.setSettingItem(item, value, setValueIsSet);
  }

  setSetting(selector: string, value: SettingValue) {
    this.setSettingImpl(selector, value, true);
  }

  setSettingDefaultValue(selector: string, value: SettingValue) {
    this.setSettingImpl(selector, value, false);
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
          valueIsSet: false,
          defaultValue: item.defaultValue,
          caption: item.caption,
          choices: item.choices,
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
        valueIsSet: false,
        defaultValue: item.defaultValue,
        caption: item.caption,
        choices: item.choices,
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

registerBuildbotSettingsSingleton(globalSettings);
