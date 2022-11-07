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

import {action, makeObservable, observable} from "mobx";

export default class SidebarStore {
  @observable pinned: boolean;
  @observable active: boolean;
  @observable inside: boolean = false;
  @observable activeGroup: string|null = null;

  constructor() {
    makeObservable(this);
    this.pinned = this.computeInitialPinned();
    this.active = this.pinned;
  }

  private computeInitialPinned() {
    const value = localStorage.getItem("sidebarPinned");
    if (value === "true") {
      return true;
    }
    if (value === "false") {
      return false;
    }
    return window.innerWidth > 800;
  }

  @action togglePinned() {
    this.pinned = !this.pinned;
    localStorage.setItem("sidebarPinned", this.pinned.toString());
  }

  @action enter() {
    this.inside = true;
  }

  @action leave() {
    this.inside = false;
  }

  @action afterLeaveDelay() {
    if (!this.inside && !this.pinned) {
      this.active = false;
      this.activeGroup = null;
    }
  }

  @action show() {
    this.active = true;
  }

  @action hide() {
    this.active = false;
    this.inside = false;
  }

  @action toggleGroup(group: string) {
    if (this.activeGroup !== group) {
      this.activeGroup = group;
    } else {
      this.activeGroup = null;
    }
  }
}