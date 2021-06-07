#!/bin/bash

export BORG_PASSPHRASE=XXXXXXXXXXXXXXXXXX
export BORG_REMOTE_PATH=borg1

borg prune --keep-weekly 4 --keep-daily 7 XXXX@XXXX.rsync.net:fileserver
borg create --stats XXXX@XXXX.rsync.net:fileserver::`date +%A` /etc /root /opt /var/www | tee -a backup.txt

rsync --delete-after -rqc /store/eBooks/ XXXX@XXXX.rsync.net:eBooks/ | tee -a backup.txt
rsync --delete-after --size-only -rq /media/Music/ XXXX@XXXX.rsync.net:Music/ | tee -a backup.txt
