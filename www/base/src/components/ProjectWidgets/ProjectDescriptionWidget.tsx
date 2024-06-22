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
import {Card} from "react-bootstrap";
import {
  Project,
  useDataAccessor,
  useDataApiQuery,
} from "buildbot-data-js";
import {TableHeading} from "../TableHeading/TableHeading";

export type ProjectDescriptionWidgetProps = {
  projectid: number;
}

export const ProjectDescriptionWidget = observer(({projectid}: ProjectDescriptionWidgetProps) => {
  const accessor = useDataAccessor([]);

  const projectQuery = useDataApiQuery(() => Project.getAll(accessor, {query: {
      projectid: projectid
    }}));
  const project = projectQuery.getNthOrNull(0);

  const renderDescription = (project: Project) => {
    if (project.description_format !== null && project.description_html !== null) {
      return (
          <div>
            <div dangerouslySetInnerHTML={{__html: project.description_html}}/>
          </div>
      )
    } else {
      return (
          <div>{project.description}</div>
      );
    }
  };

  if (project !== null && project.description === null) {
    return (
      <></>
    );
  }

  return (
    <Card>
      <Card.Body>
        <h5>Description</h5>
        {project === null ? <>...</> : renderDescription(project)}
      </Card.Body>
    </Card>
  );
});
