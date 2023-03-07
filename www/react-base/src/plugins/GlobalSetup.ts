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

import {
  GroupSettings,
  RegistrationCallbacks, RouteConfig, SettingGroupConfig
} from "../../../plugin_support/src";
import {globalMenuSettings} from "./GlobalMenuSettings";
import {globalRoutes} from "./GlobalRoutes";
import {globalSettings} from "./GlobalSettings";

declare global {
  function buildbotSetupPlugin(
    callback: (registrationCallbacks: RegistrationCallbacks) => void): void;
}

window.buildbotSetupPlugin = (callback: (registrationCallbacks: RegistrationCallbacks) => void) => {
  callback({
    registerMenuGroup: (group: GroupSettings) => { globalMenuSettings.addGroup(group); },
    registerRoute: (route: RouteConfig) => { globalRoutes.addRoute(route); },
    registerSettingGroup: (group: SettingGroupConfig) => { globalSettings.addGroup(group); },
  });
}
