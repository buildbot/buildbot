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
import {
  Builder,
  Change,
  DataCollection,
  useDataAccessor,
  useDataApiDynamicQuery,
  useDataApiQuery,
  useDataApiSingleElementQuery
} from "buildbot-data-js";
import {useParams} from "react-router-dom";
import {useState} from "react";
import {getBuildLinkDisplayProperties, ChangeDetails} from "buildbot-ui";
import {BuildsTable} from "../../components/BuildsTable/BuildsTable";
import {LoadingDiv} from "../../components/LoadingDiv/LoadingDiv";


export const ChangeBuildsView = observer(() => {
  const changeid = Number.parseInt(useParams<"changeid">().changeid ?? "");

  const accessor = useDataAccessor([changeid]);
  const buildsFetchLimit = buildbotGetSettings().getIntegerSetting('ChangeBuilds.buildsFetchLimit');

  const changeQuery = useDataApiQuery(() => Change.getAll(accessor, {id: changeid.toString()}));
  const change = changeQuery.getNthOrNull(0);

  const buildsQuery = useDataApiSingleElementQuery(change, [],
    c => c.getBuilds({query: {
        property: ["owners", "workername", "branch", "revision", ...getBuildLinkDisplayProperties()],
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

  const renderBuilds = () => {
    if (!buildsQuery.isResolved()) {
      return <LoadingDiv/>;
    }
    if (buildsQuery.array.length === 0) {
      return <>None</>
    }
    return <BuildsTable builds={buildsQuery} builders={buildersQuery}/>
  };

  return (
    <div className="container">
      { change !== null
        ? <ChangeDetails change={change} compact={false} showDetails={true} setShowDetails={null}/>
        : <LoadingDiv/>
      }
      {renderBuilds()}
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerRoute({
    route: "changes/:changeid",
    group: null,
    element: () => <ChangeBuildsView/>,
  });

  reg.registerSettingGroup({
    name:'ChangeBuilds',
    caption: 'ChangeBuilds page related settings',
    items:[{
      type: 'integer',
      name: 'buildsFetchLimit',
      caption: 'Maximum number of builds to fetch for the selected change',
      defaultValue: 10
    }]
  });
});
