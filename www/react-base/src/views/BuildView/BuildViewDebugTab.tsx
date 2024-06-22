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
import {Link} from "react-router-dom";
import {
  Build,
  Buildrequest,
  Buildset, DataCollection,
  useDataAccessor,
  useDataApiDynamicQuery,
} from "buildbot-data-js";
import {BuildLinkWithSummaryTooltip} from "../../../../ui";
import {LoadingDiv} from "../../components/LoadingDiv/LoadingDiv";
import {RawData} from "../../components/RawData/RawData";
import {TableHeading} from "../../components/TableHeading/TableHeading";

export type BuildViewDebugTabProps = {
  build: Build | null;
  buildset: Buildset | null;
  buildrequest : Buildrequest | null;
};

export const BuildViewDebugTab = observer(({build, buildset, buildrequest}:
                                             BuildViewDebugTabProps) => {
  const accessor = useDataAccessor([build?.id ?? -1]);
  const prevBuildsQuery = useDataApiDynamicQuery([build !== null],
    () => build === null
      ? new DataCollection<Build>()
      : Build.getAll(accessor, {query: {
          builderid: build.builderid,
          workerid: build.workerid,
          number__lt: build.number,
          order: '-number',
          limit: 5
      }}
    )
  );

  if (build === null || buildrequest === null || buildset === null) {
    return <TableHeading>Buildrequest:</TableHeading>;
  }

  const renderPrevBuildOnBuildDir = () => {
    if (!prevBuildsQuery.resolved) {
      return <LoadingDiv/>
    }
    if (prevBuildsQuery.array.length === 0) {
      return <>None</>;
    }
    return <>
      {
        prevBuildsQuery.array.slice(0).reverse().map(prevBuild => (
          <BuildLinkWithSummaryTooltip key={prevBuild.id} build={prevBuild}/>
        ))
      }
    </>;
  }

  return (
    <>
      <TableHeading>
        <Link to={`/buildrequests/${buildrequest.id}`}>Buildrequest:</Link>
      </TableHeading>
      <RawData data={buildrequest.toObject()}/>
      <TableHeading>Buildset:</TableHeading>
      <RawData data={buildset.toObject()}/>
      <TableHeading>Previous builds on the same build directory:</TableHeading>
      {renderPrevBuildOnBuildDir()}
    </>
  );
});
