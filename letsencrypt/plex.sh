#!/usr/bin/env bash

# File paths
PFX_PATH="/var/lib/plexmediaserver/letsencrypt.pfx"
KEY_PATH="/etc/letsencrypt/live/plex.doesthings.io/privkey.pem"
CERT_PATH="/etc/letsencrypt/live/plex.doesthings.io/cert.pem"
CHAIN_PATH="/etc/letsencrypt/live/plex.doesthings.io/chain.pem"

# Create a PKCS12 file with the certificate, private key, and certificate chain
/usr/bin/openssl pkcs12 -export \
  -out $PFX_PATH \
  -passout pass:thisisasecretpassword \
  -certpbe AES-256-CBC \
  -keypbe AES-256-CBC \
  -macalg SHA256 \
  -inkey $KEY_PATH \
  -in $CERT_PATH \
  -certfile $CHAIN_PATH

# Check if openssl command was successful
if [ $? -ne 0 ]; then
    echo "Failed to create PKCS12 file"
    exit 1
fi

# Make sure Plex can read the file
chown plex:plex $PFX_PATH

# Check if chown command was successful
if [ $? -ne 0 ]; then
    echo "Failed to change ownership of the PKCS12 file"
    exit 1
fi

# Restart Plex
/usr/bin/systemctl restart plexmediaserver

# Check if systemctl command was successful
if [ $? -ne 0 ]; then
    echo "Failed to restart Plex Media Server"
    exit 1
fi

echo "Successfully renewed and applied certificate to Plex Media Server"
