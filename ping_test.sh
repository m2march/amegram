#!/bin/bash
for i in `seq ${2} ${3}`
do
    ping -c 1 ${1}.${i} -t 1 > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "${1}.${i} responded."
    fi
done
