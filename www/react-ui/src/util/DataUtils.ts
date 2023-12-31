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

import {Builder, DataCollection, Master} from "buildbot-data-js";

export function hasActiveMaster(builder: Builder, masters: DataCollection<Master>) {
  if ((builder.masterids == null)) {
    return false;
  }
  let active = false;
  for (let mid of builder.masterids) {
    const m = masters.getByIdOrNull(mid);
    if (m !== null && m.active) {
      active = true;
    }
  }
  if (builder.tags.includes('_virtual_')) {
    active = true;
  }
  return active;
};
