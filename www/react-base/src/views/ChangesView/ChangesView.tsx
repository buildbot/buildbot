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
import {useDataAccessor, useDataApiQuery} from "../../data/ReactUtils";
import {globalMenuSettings} from "../../plugins/GlobalMenuSettings";
import {globalRoutes} from "../../plugins/GlobalRoutes";
import {globalSettings} from "../../plugins/GlobalSettings";
import {Change} from "../../data/classes/Change";
import ChangesTable from "../../components/ChangesTable/ChangesTable";


const ChangesView = observer(() => {
  const accessor = useDataAccessor([]);

  const changesFetchLimit = globalSettings.getIntegerSetting("Changes.changesFetchLimit");
  const changesQuery = useDataApiQuery(
    () => Change.getAll(accessor, {query: {limit: changesFetchLimit, order: '-changeid'}}));

  return (
    <div className="container">
      <ChangesTable changes={changesQuery}/>
    </div>
  );
});

globalMenuSettings.addGroup({
  name: 'changes',
  parentName: 'builds',
  caption: 'Last Changes',
  icon: null,
  order: null,
  route: '/changes',
});

globalRoutes.addRoute({
  route: "changes",
  group: "builds",
  element: () => <ChangesView/>,
});

globalSettings.addGroup({
  name: 'Changes',
  caption: 'Changes page related settings',
  items: [{
    type: 'integer',
    name: 'changesFetchLimit',
    caption: 'Maximum number of changes to fetch',
    defaultValue: 50
  }]});

export default ChangesView;
