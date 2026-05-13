#!/usr/bin/sh

cd /home/pi || exit -1
if [ -f test.pyc ]; then
  python3 test.pyc
elif [ -f test.py ]; then
  python3 test.py
fi
