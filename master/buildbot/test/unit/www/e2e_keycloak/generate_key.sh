#!/bin/bash

openssl req -x509 -newkey rsa:4096 -nodes -keyout key.pem -out cert.pem -sha256 -days 365 \
    -subj "/CN=localhost"
