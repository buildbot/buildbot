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
import {Buildrequest, Buildset} from "buildbot-data-js";
import {RawData} from "../../components/RawData/RawData";
import {TableHeading} from "../../components/TableHeading/TableHeading";

export type BuildViewDebugTabProps = {
  buildset: Buildset | null;
  buildrequest : Buildrequest | null;
};

export const BuildViewDebugTab = observer(({buildset, buildrequest}: BuildViewDebugTabProps) => {
  if (buildrequest === null || buildset === null) {
    return <TableHeading>Buildrequest:</TableHeading>;
  }

  return (
    <>
      <TableHeading>
        <Link to={`/buildrequests/${buildrequest.id}`}>Buildrequest:</Link>
      </TableHeading>
      <RawData data={buildrequest.toObject()}/>
      <TableHeading>Buildset:</TableHeading>
      <RawData data={buildset.toObject()}/>
    </>
  );
});
