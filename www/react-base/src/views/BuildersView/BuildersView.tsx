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

import './BuildersView.scss';
import {observer} from "mobx-react";
import {useState} from "react";
import {FaCogs} from "react-icons/fa";
import {buildbotGetSettings, buildbotSetupPlugin} from "buildbot-plugin-support";
import {
  Builder,
  DataCollection,
  Master,
  Worker,
  useDataAccessor,
  useDataApiQuery
} from "buildbot-data-js";
import {
  TagFilterManager,
  hasActiveMaster,
  useTagFilterManager,
  useTopbarItems,
} from "buildbot-ui";
import {BuildersTable} from "../../components/BuildersTable/BuildersTable";
import {SettingCheckbox} from "../../components/SettingCheckbox/SettingCheckbox";

const isBuilderFiltered = (builder: Builder, filterManager: TagFilterManager,
                           masters: DataCollection<Master>, showOldBuilders: boolean) => {
  if (!showOldBuilders && !hasActiveMaster(builder, masters)) {
    return false;
  }
  return filterManager.shouldShowByTags(builder.tags);
};

export const BuildersView = observer(() => {
  const accessor = useDataAccessor([]);

  const filterManager = useTagFilterManager("tags");
  const [builderNameFilter, setBuilderNameFilter] = useState("");

  useTopbarItems([
    {caption: "Builders", route: "/builders"}
  ]);

  const showOldBuilders = buildbotGetSettings().getBooleanSetting("Builders.show_old_builders");

  // as there is usually lots of builders, its better to get the overall
  // list of workers, masters, and builds and then associate by builder
  const builders= useDataApiQuery(() => Builder.getAll(accessor));
  const masters= useDataApiQuery(() => Master.getAll(accessor));
  const workers= useDataApiQuery(() => Worker.getAll(accessor));

  const filteredBuilders = builders.array.filter(builder => {
    return isBuilderFiltered(builder, filterManager, masters, showOldBuilders) &&
        (builderNameFilter === null || builder.name.indexOf(builderNameFilter) >= 0)
  }).sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="bb-builders-view-container">
      <form role="search" style={{width: "150px"}}>
        <input type="text" value={builderNameFilter}
               onChange={e => setBuilderNameFilter(e.target.value)}
               placeholder="Search for builders" className="bb-builders-view-form-control"/>
      </form>
      <BuildersTable builders={filteredBuilders} allWorkers={workers}
                     isLoading={!builders.isResolved() || !workers.isResolved()}
                     filterManager={filterManager}/>
      <div>
        <SettingCheckbox value={showOldBuilders} label="Show old builders"
                         settingSelector="Builders.show_old_builders"/>
      </div>
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerMenuGroup({
    name: 'builds',
    parentName: null,
    caption: 'Builds',
    icon: <FaCogs/>,
    order: 10,
    route: null,
  });

  reg.registerMenuGroup({
    name: 'builders',
    parentName: 'builds',
    caption: 'Builders',
    order: null,
    route: '/builders',
  });

  reg.registerRoute({
    route: "builders",
    group: "builders",
    element: () => <BuildersView/>,
  });

  reg.registerSettingGroup({
    name: 'Builders',
    caption: 'Builders page related settings',
    items: [{
      type: 'boolean',
      name: 'show_old_builders',
      caption: 'Show old builders',
      defaultValue: false
    }, {
      type: 'boolean',
      name: 'show_workers_name',
      caption: 'Show workers name',
      defaultValue: false
    }, {
      type: 'integer',
      name: 'buildFetchLimit',
      caption: 'Maximum number of builds to fetch',
      defaultValue: 200
    }, {
      type:'integer',
      name:'page_size',
      caption:'Number of builders to show per page',
      defaultValue: 100
    }
  ]});
});
