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

import TopbarActionsStore from "../../stores/TopbarActionsStore";
import {observer} from "mobx-react";

export type TopbarAction = {
  caption: string;
  icon?: string;
  help?: string;
  extraClass?: string;
  action: () => void;
}

type TopbarActionsProps = {
  store: TopbarActionsStore;
}

const TopbarActions = observer(({store}: TopbarActionsProps) => {
  const elements = store.actions.map(action => {
    return (
      <div className="form-group">
        <button className={"btn btn-default " + (action.extraClass ?? "")} type="button"
                onClick={action.action} title={action.help ?? ""}>
          {action.icon ?  <><i className={"fa fa-" + action.icon}></i><span>&nbsp;</span></> : <></> }
          {action.caption}
        </button>
        &nbsp;
      </div>
    );
  });

  return (
    <form className="navbar-form navbar-left">
      {elements}
    </form>
  );
});

export default TopbarActions;
