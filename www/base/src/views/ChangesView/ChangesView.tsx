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

import {observer} from "mobx-react";
import {buildbotGetSettings, buildbotSetupPlugin} from "buildbot-plugin-support";
import {Change, useDataAccessor, useDataApiDynamicQuery} from "buildbot-data-js";
import {useLoadMoreItemsState} from "buildbot-ui";
import {ChangesTable} from "../../components/ChangesTable/ChangesTable";

export const ChangesView = observer(() => {
  const accessor = useDataAccessor([]);

  const initialChangesFetchLimit = buildbotGetSettings().getIntegerSetting("Changes.changesFetchLimit");
  const [changesFetchLimit, onLoadMoreChanges] =
      useLoadMoreItemsState(initialChangesFetchLimit, initialChangesFetchLimit);

  const changesQuery = useDataApiDynamicQuery([changesFetchLimit],
    () => Change.getAll(accessor, {query: {limit: changesFetchLimit, order: '-changeid'}}));

  return (
    <div className="container">
      <ChangesTable changes={changesQuery} fetchLimit={changesFetchLimit} onLoadMore={onLoadMoreChanges}/>
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerMenuGroup({
    name: 'changes',
    parentName: 'builds',
    caption: 'Last Changes',
    order: null,
    route: '/changes',
  });

  reg.registerRoute({
    route: "changes",
    group: "builds",
    element: () => <ChangesView/>,
  });

  reg.registerSettingGroup({
    name: 'Changes',
    caption: 'Changes page related settings',
    items: [{
      type: 'integer',
      name: 'changesFetchLimit',
      caption: 'Initial number of changes to fetch',
      defaultValue: 50
    }]
  });
});
