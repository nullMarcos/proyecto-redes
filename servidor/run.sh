#! /bin/bash

alembic upgrade head
python3 server.py