import './MessageInfo.scss';
import React, { useState, useEffect } from 'react';
import {FaStackExchange, FaRegWindowClose } from "react-icons/fa";

import {
    MessageInfoClass,
    useDataAccessor,
    useDataApiQuery
  } from "buildbot-data-js";
import { reaction } from 'mobx';


interface MessageInfoData {
    messages?: string[];
}

export const MessageInfo: React.FC<MessageInfoData> = ({ }) => {
    const [data, setData] = useState<MessageInfoData | null>(null);
    const [isOpen, setIsOpen] = useState(false);
    const accessor = useDataAccessor([]);
    const mastersQuery = useDataApiQuery(() => MessageInfoClass.getAll(accessor));

    reaction(
        () => mastersQuery.array.slice(),
        array => {
          if (array.length > 0) {
            fetchData();
          }
        }
      );

    const handleClose = (event: React.MouseEvent) => {
        event.stopPropagation();
        setIsOpen(false);
    };
    const fetchData = async () => {
        const builderQuery = mastersQuery.array.slice();
        const results = builderQuery.map(instance => instance.toObject());
        if (results.length > 0) {
          const messages = results.map(result => result.message);
          setData({ messages: messages });
        }
      }

    useEffect(() => {
        fetchData();

    }, []);

    useEffect(() => {
        if(data?.messages) {
            setIsOpen(true);
        }
    }, [data?.messages]);

    return (
        <>
        {data?.messages ? (isOpen ? (
                <div className={`message-info ${isOpen ? 'open' : 'closed'}`}>
                    {data?.messages.map((msg, index) => (
                        <p key={index}>{msg}</p>
                    ))}
                    <FaRegWindowClose  onClick={handleClose} className="close-button"/>
                </div>
            ) : <FaStackExchange  className="float-icon" onClick={() => setIsOpen(true)}/>
            ) : null}
        </>
    );
};
