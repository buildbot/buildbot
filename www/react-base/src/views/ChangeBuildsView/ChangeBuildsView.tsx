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
import {
  useDataAccessor,
  useDataApiDynamicQuery,
  useDataApiQuery,
  useDataApiSingleElementQuery
} from "../../data/ReactUtils";
import {globalRoutes} from "../../plugins/GlobalRoutes";
import {globalSettings} from "../../plugins/GlobalSettings";
import {Change} from "../../data/classes/Change";
import {useParams} from "react-router-dom";
import {useState} from "react";
import DataCollection from "../../data/DataCollection";
import {Builder} from "../../data/classes/Builder";
import ChangeDetails from "../../components/ChangeDetails/ChangeDetails";
import BuildsTable from "../../components/BuildsTable/BuildsTable";


const ChangeBuildsView = observer(() => {
  const changeid = Number.parseInt(useParams<"changeid">().changeid ?? "");

  const accessor = useDataAccessor([changeid]);
  const buildsFetchLimit = globalSettings.getIntegerSetting('ChangeBuilds.buildsFetchLimit');

  const changeQuery = useDataApiQuery(() => Change.getAll(accessor, {id: changeid.toString()}));
  const change = changeQuery.getNthOrNull(0);

  const buildsQuery = useDataApiSingleElementQuery(change,
    c => c.getBuilds({query: {
        property: ["owners", "workername"],
        limit: buildsFetchLimit
      }}));

  const builderIds = Array.from(new Set(buildsQuery.array.map(build => build.builderid)));

  const buildersQuery = useDataApiDynamicQuery(builderIds,
    () => {
      // Don't request builders when we haven't loaded builds yet
      if (builderIds.length === 0) {
        return new DataCollection<Builder>();
      }
      return Builder.getAll(accessor, {query: {builderid__eq: builderIds}})
    });

  const [showDetails, setShowDetails] = useState(false);

  return (
    <div className="container">
      { change !== null
        ? <ChangeDetails change={change} compact={false}
                         showDetails={showDetails} setShowDetails={setShowDetails}/>
        : <div>Loading... </div>
      }
      { buildsQuery.array.length > 0
        ? <BuildsTable builds={buildsQuery} builders={buildersQuery}/>
        : <div>Loading... </div>
      }
    </div>
  );
});

globalRoutes.addRoute({
  route: "changes/:changeid",
  group: null,
  element: () => <ChangeBuildsView/>,
});

globalSettings.addGroup({
  name:'ChangeBuilds',
  caption: 'ChangeBuilds page related settings',
  items:[{
    type: 'integer',
    name: 'buildsFetchLimit',
    caption: 'Maximum number of builds to fetch for the selected change',
    defaultValue: 10
  }]});

export default ChangeBuildsView;
