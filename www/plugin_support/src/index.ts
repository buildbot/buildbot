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

export type GroupSettings = {
  name: string;
  parentName: string | null;
  caption: string;
  route: string | null;
  icon?: JSX.Element;
  order: number | null;
};

export type RouteConfig = {
  route: string;
  group: string | null;
  element: () => JSX.Element;
}

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

export type RegistrationCallbacks = {
  registerMenuGroup: (group: GroupSettings) => void;
  registerRoute: (route: RouteConfig) => void;
  registerSettingGroup: (group: SettingGroupConfig) => void;
}

export interface ISettings {
  getIntegerSetting(selector: string): number;
  getFloatSetting(selector: string): number;
  getStringSetting(selector: string): string;
  getBooleanSetting(selector: string): boolean;
  setSetting(selector: string, value: SettingValue): void;
  save(): void;
};

declare global {
  function buildbotSetupPlugin(
    callback: (registrationCallbacks: RegistrationCallbacks) => void): void;

  function buildbotGetSettings(): ISettings;
}
