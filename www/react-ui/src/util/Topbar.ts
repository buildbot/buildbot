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

import {useContext, useEffect} from "react";
import {TopbarContext} from "../contexts/Topbar";
import {TopbarAction, TopbarItem} from "../stores/TopbarStore";

export function useTopbarItems(items: TopbarItem[]) {
  const store = useContext(TopbarContext);

  useEffect(() => {
    store.setItems(items);
  }, [store, items]);

  // We only want to clear the items once, thus the useEffect hook is split into two parts, one
  // for updates, one for eventual cleanup when navigating out of view.
  useEffect(() => {
    return () => store.setItems([]);
  }, [store])
}

export function useTopbarActions(actions: TopbarAction[]) {
  const store = useContext(TopbarContext);

  useEffect(() => {
    store.setActions(actions);
  }, [actions, store]);

  // We only want to clear the items once, thus the useEffect hook is split into two parts, one
  // for updates, one for eventual cleanup when navigating out of view.
  useEffect(() => {
    return () => store.setActions([]);
  }, [store])
}
