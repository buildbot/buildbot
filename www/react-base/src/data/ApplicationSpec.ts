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

import DataClient from "./DataClient";
import {useEffect, useState} from "react";

export type EndpointFieldSpec = {
  name: string;
  type: string;
  type_spec: EndpointTypeSpec;
}

export type EndpointTypeSpec = {
  name?: string;
  type?: string;
  can_be_null?: boolean;
  of?: EndpointTypeSpec;
  fields?: EndpointFieldSpec[];
}

export type EndpointDescription = {
  path: string;
  plural: string;
  type: string;
  type_spec: EndpointTypeSpec;
}

export const useApplicationSpec = (dataClient: DataClient) => {
  const [result, setResult] = useState<EndpointDescription[]>([]);

  useEffect(() => {
    const performRequest = async () => {
      const response = await dataClient.restClient.get('application.spec');
      setResult(response.specs as EndpointDescription[]);
    }
    performRequest();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return result;
}
