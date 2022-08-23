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
import {
  action,
  autorun,
  computed,
  IObservableArray,
  makeObservable,
  observable,
  ObservableMap
} from "mobx";
import DataCollection, {IDataCollection} from "./DataCollection";
import {IReactionDisposer} from "mobx";

/* This class wraps multiple DataCollections of the same thing.
 */
export default class DataMultiCollection<ParentDataType extends BaseClass,
    DataType extends BaseClass> implements IDataCollection {

  parentArray: IObservableArray<ParentDataType> | null;
  parentArrayMap: ObservableMap<string, DataCollection<ParentDataType>> | null;
  parentFilteredIds: IObservableArray<string>;

  @observable byParentId = observable.map<string, DataCollection<DataType>>();
  @observable sortedParentIds = observable.array<string>();
  callback: (child: ParentDataType) => DataCollection<DataType>;
  private disposer: IReactionDisposer;

  constructor(parentArray: IObservableArray<ParentDataType> | null,
              parentArrayMap: ObservableMap<string, DataCollection<ParentDataType>> | null,
              parentFilteredIds: IObservableArray<string> | null,
              callback: (child: ParentDataType) => DataCollection<DataType>) {
    makeObservable(this);
    this.parentArray = parentArray;
    this.parentArrayMap = parentArrayMap;
    this.parentFilteredIds = parentFilteredIds ?? observable([]);

    this.callback = callback;
    if (parentArray !== null) {
      this.disposer = autorun(() => {
        const newParentIds = new Set<string>();
        for (let parent of this.parentArray!) {
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
    } else if (parentArrayMap !== null) {
      this.disposer = autorun(() => {
        const newParentIds = new Set<string>();
        for (const parentList of this.parentArrayMap!.values()) {
          for (const parent of parentList.array) {
            if (!this.parentFilteredIds.indexOf(parent.id)) {
              continue;
            }

            newParentIds.add(parent.id);
            if (!this.byParentId.has(parent.id)) {
              this.addByParentId(parent.id, this.callback(parent));
            }
          }
        }
        for (let key of this.byParentId.keys()) {
          if (!newParentIds.has(key)) {
            this.removeByParentId(key);
          }
        }
      });
    } else {
      throw Error("Either parentArray or parentArrayMap must not be null");
    }
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
    this.sortedParentIds.push(id);
    this.sortedParentIds.sort();
  }

  @action removeByParentId(id: string) {
    this.byParentId.get(id)?.close();
    this.byParentId.delete(id);
    this.sortedParentIds.remove(id);
  }

  getRelated<ChildDataType extends BaseClass>(
    callback: (child: DataType) => DataCollection<ChildDataType>) {
    return new DataMultiCollection<DataType, ChildDataType>(null, this.byParentId, null, callback);
  }

  // Acquires nth element across all collections tracked by this multi collection. The iteration
  // order is in ascending order of parent IDs.
  getNthOrNull(index: number): DataType | null {
    for (const parentId of this.sortedParentIds) {
      const parent = this.byParentId.get(parentId);
      if (parent === undefined) {
        continue;
      }
      if (index < parent.array.length) {
        return parent.array[index];
      }
      index -= parent.array.length;
    }
    return null;
  }

  getAll(): DataType[] {
    const all: DataType[] = [];
    for (const parentId of this.sortedParentIds) {
      const parent = this.byParentId.get(parentId);
      if (parent === undefined) {
        continue;
      }
      all.push(...parent.array);
    }
    return all;
  }

  getNthOfParentOrNull(parentId: string, index: number): DataType | null {
    const collection = this.byParentId.get(parentId);
    if (collection === undefined) {
      return null;
    }
    if (index >= collection.array.length) {
      return null;
    }
    return collection.array[index];
  }

  getParentCollectionOrEmpty(parentId: string): DataCollection<DataType> {
    const collection = this.byParentId.get(parentId);
    if (collection === undefined) {
      return new DataCollection<DataType>();
    }
    return collection;
  }
}
