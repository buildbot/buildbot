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

import BaseClass from "./classes/BaseClass";
import {action, autorun, IObservableArray, makeObservable, observable} from "mobx";
import DataCollection, {IDataCollection} from "./DataCollection";
import {IReactionDisposer} from "mobx";

/* This class wraps multiple DataCollections of the same thing.
 */
export default class DataMultiCollection<ParentDataType extends BaseClass,
    DataType extends BaseClass> implements IDataCollection {

  parentArray: IObservableArray<ParentDataType>;
  @observable byParentId = observable.map<string, DataCollection<DataType>>();
  callback: (child: ParentDataType) => DataCollection<DataType>;
  private disposer: IReactionDisposer;

  constructor(parentArray: IObservableArray<ParentDataType>,
              callback: (child: ParentDataType) => DataCollection<DataType>) {
    makeObservable(this);
    this.parentArray = parentArray;
    this.callback = callback;
    this.disposer = autorun(() => {
      const newParentIds = new Set<string>();
      for (let parent of this.parentArray) {
        newParentIds.add(parent.id);
        if (!this.byParentId.has(parent.id)) {
          this.addByParentId(parent.id, this.callback(parent));
        }
      }
      for (let key of this.byParentId.keys()) {
        if (!newParentIds.has(key)) {
          this.removeByParentId(key);
        }
      }
    });
  }

  subscribe() {
    return Promise.resolve();
  }

  initial(data: any[]) {}

  close() : Promise<void> {
    this.disposer();
    return Promise.all(Object.values(this.byParentId).map((collection => collection.close()))).then();
  }

  @action addByParentId(id: string, collection: DataCollection<DataType>) {
    this.byParentId.set(id, collection);
  }

  @action removeByParentId(id: string) {
    this.byParentId.get(id)!.close();
    this.byParentId.delete(id);
  }
}
