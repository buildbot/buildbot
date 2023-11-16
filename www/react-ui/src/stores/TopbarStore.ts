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

import {action, IObservableArray, makeObservable, observable} from "mobx";
import {ButtonVariant} from "react-bootstrap/types";

export type TopbarItem = {
  route: string | null,
  caption: string
}

export type TopbarAction = {
  caption: string;
  icon?: JSX.Element;
  help?: string;
  variant?: ButtonVariant;
  action: () => void;
}

export class TopbarStore {
  items: IObservableArray<TopbarItem> = observable<TopbarItem>([]);
  actions: IObservableArray<TopbarAction> = observable<TopbarAction>([]);

  constructor() {
    makeObservable(this);
  }

  @action setItems(items: TopbarItem[]) {
    this.items.replace(items);
  }

  @action clearItems() {
    this.items.clear();
  }

  @action setActions(actions: TopbarAction[]) {
    this.actions.replace(actions);
  }

  @action clearActions() {
    this.actions.clear();
  }
}
