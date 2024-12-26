/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {action, makeObservable, observable} from "mobx";
import {BaseClass} from "./BaseClass";
import {IDataDescriptor} from "./DataDescriptor";
import {IDataAccessor} from "../DataAccessor";
import {RequestQuery} from "../DataQuery";

export class MessageInfoClass extends BaseClass {
  @observable filename!: string;
  @observable message!: string;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.filename));
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.filename = object.filename;
    this.message = object.message;
  }

  toObject() {
    return {
      filename: this.filename,
      message: this.message,
    };
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<MessageInfoClass>("messagesinfo", query, messageInfoDescriptor);
  }
}

export class MessageInfoDescriptor implements IDataDescriptor<MessageInfoClass> {
  restArrayField = "messagesinfo";
  fieldId: string = "filename";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new MessageInfoClass(accessor, endpoint, object);
  }
}

export const messageInfoDescriptor = new MessageInfoDescriptor();
