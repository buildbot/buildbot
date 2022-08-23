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
  parentFilteredIds: IObservableArray<string>;
  @observable byParentId = observable.map<string, DataCollection<DataType>>();
  callback: (child: ParentDataType) => DataCollection<DataType>;
  private disposer: IReactionDisposer;

  constructor(parentArray: IObservableArray<ParentDataType>,
              parentFilteredIds: IObservableArray<string> | null,
              callback: (child: ParentDataType) => DataCollection<DataType>) {
    makeObservable(this);
    this.parentArray = parentArray;
    this.parentFilteredIds = parentFilteredIds ?? observable([]);

    this.callback = callback;
    this.disposer = autorun(() => {
      const newParentIds = new Set<string>();
      for (let parent of this.parentArray) {
        if (!this.parentFilteredIds.indexOf(parent.id)) {
          continue;
        }

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

  getNthOfParentOrNull<DataType extends BaseClass>(parentId: string, index: number): DataType | null {
    if (!(parentId in this.byParentId)) {
      return null;
    }

    // FIXME: this should be enforced by the typescript type system (that is, it shouldn't be
    // possible to call this function if it contains wrong collection.
    const collection = this.byParentId[parentId] as unknown as DataCollection<DataType>;
    if (index >= collection.array.length) {
      return null;
    }
    return collection.array[index];
  }

  getParentCollectionOrEmpty<DataType extends BaseClass>(parentId: string): Collection {
    if (!(parentId in this.byParentId)) {
      // FIXME: this should be enforced by the typescript type system (that is, it shouldn't be
      // possible to call this function if it contains wrong collection.
      return new DataCollection<DataType>() as unknown as Collection;
    }

    return this.byParentId[parentId];
  }
}
