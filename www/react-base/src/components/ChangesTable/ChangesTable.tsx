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

import './ChangesTable.scss';
import {action, makeObservable, observable} from "mobx";
import {FaMinus, FaPlus} from "react-icons/fa";
import {Link} from "react-router-dom";
import {Change, DataCollection} from "buildbot-data-js";
import {ChangeDetails} from "buildbot-ui";
import {observer, useLocalObservable} from "mobx-react";
import {resizeArray} from "../../util/Array";
import {LoadingSpan} from "../LoadingSpan/LoadingSpan";

class ChangesTableState {
  showDetails = observable.array<boolean>();

  constructor() {
    makeObservable(this);
  }

  @action resizeTable(size: number, newValue: boolean) {
    resizeArray(this.showDetails, size, newValue);
  }

  @action setShowDetailsAll(show: boolean) {
    this.showDetails.fill(show);
  }

  @action setShowDetailsSingle(index: number, show: boolean) {
    this.showDetails[index] = show;
  }
}

type ChangesTableProps = {
  changes: DataCollection<Change>
}

export const ChangesTable = observer(({changes}: ChangesTableProps) => {
  const tableState = useLocalObservable(() => new ChangesTableState());
  tableState.resizeTable(changes.array.length, false);

  const changeElements = changes.array.map((change, index) => {
    return (
      <li key={change.id} className="list-group-item">
        <Link to={`/changes/${change.id}`}>See builds</Link>
        <ChangeDetails change={change} compact={false} showDetails={tableState.showDetails[index]}
                       setShowDetails={(show) => tableState.setShowDetailsSingle(index, show)}/>
      </li>
    );
  });

  const renderChangesCount = () => {
    if (changes.isResolved()) {
      return <>{changes.array.length} changes</>;
    }
    return <LoadingSpan/>
  }

  return (
    <div className="container-fluid">
      <div className="navbar navbar-default">
        <div className="container-fluid">
          <div className="navbar-header">
            <div className="navbar-brand">{renderChangesCount()}</div>
          </div>
          <div className="navbar-form navbar-right">
            <div className="form-group">
              <div onClick={() => tableState.setShowDetailsAll(false)} title="Collapse all"
                   className="btn btn-default">
                <FaMinus/>
              </div>
              <div onClick={() => tableState.setShowDetailsAll(true)} title="Expand all"
                   className="btn btn-default">
                <FaPlus/>
              </div>
            </div>
          </div>
        </div>
      </div>
      <ul className="bb-changes-table-list list-group">
        {changeElements}
      </ul>
    </div>
  );
});
