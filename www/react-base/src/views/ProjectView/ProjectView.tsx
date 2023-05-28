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

import './ProjectView.scss';
import {observer} from "mobx-react";
import {
  Builder,
  DataCollection, Master,
  Project,
  useDataAccessor,
  useDataApiQuery,
  useDataApiSingleElementQuery, Worker
} from "buildbot-data-js";
import {useState} from "react";
import {hasActiveMaster, TagFilterManager, useTagFilterManager, useTopbarItems} from "buildbot-ui";
import {useParams} from "react-router-dom";
import {buildbotGetSettings, buildbotSetupPlugin} from "buildbot-plugin-support";
import {BuildersTable} from "../../components/BuildersTable/BuildersTable";
import {SettingCheckbox} from "../../components/SettingCheckbox/SettingCheckbox";

const isBuilderFiltered = (builder: Builder, filterManager: TagFilterManager,
                           masters: DataCollection<Master>, showOldBuilders: boolean) => {
  if (!showOldBuilders && !hasActiveMaster(builder, masters)) {
    return false;
  }
  return filterManager.shouldShowByTags(builder.tags);
};

export const ProjectView = observer(() => {
  const projectid = Number.parseInt(useParams<"projectid">().projectid ?? "");

  const accessor = useDataAccessor([]);

  const filterManager = useTagFilterManager("tags");
  const [builderNameFilter, setBuilderNameFilter] = useState("");

  const projectQuery = useDataApiQuery(() => Project.getAll(accessor, {query: {
      projectid: projectid
    }}));
  const project = projectQuery.getNthOrNull(0);
  const builders = useDataApiSingleElementQuery(project, p => p.getBuilders());

  useTopbarItems([
    {caption: "Projects", route: "/projects"},
    {caption: project !== null ? project.name : "...", route: `/projects/${projectid}`}
  ]);

  const showOldBuilders = buildbotGetSettings().getBooleanSetting("Builders.show_old_builders");

  // as there is usually lots of builders, it's better to get the overall
  // list of workers, masters, and builds and then associate by builder
  const masters= useDataApiQuery(() => Master.getAll(accessor));
  const workers= useDataApiQuery(() => Worker.getAll(accessor));

  const filteredBuilders = builders.array.filter(builder => {
    return isBuilderFiltered(builder, filterManager, masters, showOldBuilders) &&
        (builderNameFilter === null || builder.name.indexOf(builderNameFilter) >= 0)
  }).sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="bb-project-view-container">
      <form role="search" style={{width: "150px"}}>
        <input type="text" value={builderNameFilter}
               onChange={e => setBuilderNameFilter(e.target.value)}
               placeholder="Search for builders" className="bb-builders-view-form-control"/>
      </form>
      <BuildersTable builders={filteredBuilders} allWorkers={workers} filterManager={filterManager}/>
      <div>
        <SettingCheckbox value={showOldBuilders} label="Show old builders"
                         settingSelector="Builders.show_old_builders"/>
      </div>
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerRoute({
    route: "projects/:projectid",
    group: null,
    element: () => <ProjectView/>,
  });
});
