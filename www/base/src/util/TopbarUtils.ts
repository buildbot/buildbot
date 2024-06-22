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

import {TopbarItem} from "buildbot-ui";
import {Builder, Project} from "buildbot-data-js";

export function buildTopbarItemsForBuilder(builder: Builder|null, project: Project|null,
                                           extraItems: TopbarItem[]) {
  const topbarItems: TopbarItem[] = [];
  if (builder !== null) {
    topbarItems.push({caption: "Builders", route: "/builders"});
    if (project !== null) {
      topbarItems.push({caption: project.name, route: `/projects/${builder.projectid}`});
    }
    topbarItems.push({caption: builder.name, route: `/builders/${builder.id}`});
  } else {
    topbarItems.push({caption: "...", route: null});
  }
  topbarItems.push(...extraItems);
  return topbarItems;
}
