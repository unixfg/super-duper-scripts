#!/bin/bash

/usr/bin/certbot renew -q --authenticator dns --dns-credentials /root/gandi.ini

openssl pkcs12 -export -out /store/PMS/letsencrypt.pfx -passout pass:plexmediaserver -inkey /etc/letsencrypt/live/plex.joshandryan.net/privkey.pem -in /etc/letsencrypt/live/plex.joshandryan.net/cert.pem -certfile /etc/letsencrypt/live/plex.joshandryan.net/chain.pem

systemctl restart plexmediaserver
systemctl restart apache2
