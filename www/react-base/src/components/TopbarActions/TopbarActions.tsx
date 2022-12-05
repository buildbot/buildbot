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
import {Button, Form} from "react-bootstrap";
import {ButtonVariant} from "react-bootstrap/types";
import React from "react";

export type TopbarAction = {
  caption: string;
  icon?: string;
  help?: string;
  variant?: ButtonVariant;
  action: () => void;
}

type TopbarActionsProps = {
  store: TopbarActionsStore;
}

const TopbarActions = observer(({store}: TopbarActionsProps) => {
  const elements = store.actions.map((action, index) => {
    return (
      <React.Fragment key={index}>
        <Button variant={action.variant ?? "light"} onClick={action.action} title={action.help ?? ""}>
          {action.icon ?  <><i className={"fa fa-" + action.icon}></i><span>&nbsp;</span></> : <></> }
          {action.caption}
        </Button>
        &nbsp;
      </React.Fragment>
    );
  });

  return (
    <Form>
      {elements}
    </Form>
  );
});

export default TopbarActions;
