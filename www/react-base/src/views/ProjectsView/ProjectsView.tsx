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

import './ProjectsView.scss';
import {observer} from "mobx-react";
import {useState} from "react";
import {FaStickyNote} from "react-icons/fa";
import {buildbotSetupPlugin} from "buildbot-plugin-support";
import {
  Project,
  useDataAccessor,
  useDataApiQuery,
} from "buildbot-data-js";
import {Link} from "react-router-dom";
import {useTopbarItems} from "buildbot-ui";

export const ProjectsView = observer(() => {
  const accessor = useDataAccessor([]);

  const [projectNameFilter, setProjectNameFilter] = useState("");

  useTopbarItems([
    {caption: "Projects", route: "/projects"}
  ]);

  const projects = useDataApiQuery(
    () => Project.getAll(accessor, {query: {active: true}}));

  const filteredProjects = projects.array.filter(project => {
    return project.name.indexOf(projectNameFilter) >= 0;
  }).sort((a, b) => a.name.localeCompare(b.name));

  const projectRowElements = filteredProjects.map(project => {
    return (
      <Link to={`/projects/${project.projectid}`}>
        <li key={project.projectid} className="list-group-item">
            {project.name}
        </li>
      </Link>
    );
  });

  return (
    <div className="bb-projects-view-container">
      <form role="search" style={{width: "150px"}}>
        <input type="text" value={projectNameFilter}
               onChange={e => setProjectNameFilter(e.target.value)}
               placeholder="Search for projects" className="bb-projects-view-form-control"/>
      </form>
      <ul className="bb-projects-view-list list-group">
        {projectRowElements}
      </ul>
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerMenuGroup({
    name: 'projects',
    parentName: null,
    caption: 'Projects',
    icon: <FaStickyNote/>,
    order: 9,
    route: '/projects',
  });

  reg.registerRoute({
    route: "projects",
    group: "projects",
    element: () => <ProjectsView/>,
  });
});
