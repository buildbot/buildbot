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

import {createContext} from "react";

export type AuthConfig = {
  name: string;
  oauth2: boolean;
  fa_icon: string;
  autologin: boolean;
}

export type AvatarConfig = {
  name: string;
}

export type UserConfig = {
  anonymous: boolean;
  username?: string;
  email?: string;
  full_name?: string;
}

export type Config = {
  title: string;
  titleURL: string;
  buildbotURL: string;
  buildbotURLs?: string[];
  multiMaster: boolean;
  ui_default_config: {[key: string]: any};
  versions: string[][];
  auth: AuthConfig;
  avatar_methods: AvatarConfig[];
  plugins: {[key: string]: any};
  user: UserConfig;
  port: string;
  // Added by the frontend itself if it's running via a proxy.
  isProxy?: boolean;
}

export const ConfigContext = createContext<Config>(undefined as any);
