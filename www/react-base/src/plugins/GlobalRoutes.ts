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

import {action, makeObservable, observable, ObservableMap} from "mobx";

export type RouteConfig = {
  route: string;
  group: string | null;
  element: () => JSX.Element;
}

export class GlobalRoutes {
  @observable configs = new ObservableMap<string, RouteConfig>();

  constructor() {
    makeObservable(this);
  }

  @action addRoute(config: RouteConfig) {
    if (this.configs.has(config.route)) {
      // It is an error in a production app to have multiple route configs with the same route.
      // However, this also happens whenever page source is hot-reloaded, therefore old value
      // is simply replaced
      console.log(`Duplicate route ${config.route}`);
    }
    this.configs.set(config.route, config);
  }
}

export const globalRoutes = new GlobalRoutes();
