#!/bin/bash
# retreive current external IP address from Cloudflare
MY_IP=$(curl -s https://icanhazip.com/)

# get the existing record from Google
GOOG=$(dig @8.8.8.8 +short home.joshandryan.net)

if [[ "$MY_IP" != "$GOOG" ]]
then

# Gandi livedn API KEY
APIKEY="XXXXXXXXXXXXXXXXXXXXXXXX"

# Static Domain hosted at Gandi
DOMAIN="joshandryan.net"

# Dynamic Subdomain
SUBDOMAIN="home"

#Get the current Zone for the provided domain
CURRENT_ZONE_HREF=$(curl -s -H "X-Api-Key: $APIKEY" https://dns.api.gandi.net/api/v5/domains/$DOMAIN | jq -r '.zone_records_href')

# Update the A reccord of the Dynamic Subdomain by PUTing on the current zone
curl -D- -X PUT -H "Content-Type: application/json" \
        -H "X-Api-Key: $APIKEY" \
        -d "{\"rrset_name\": \"$SUBDOMAIN\",
             \"rrset_type\": \"A\",
             \"rrset_ttl\": 1200,
             \"rrset_values\": [\"$MY_IP\"]}" \
        $CURRENT_ZONE_HREF/$SUBDOMAIN/A

elif [[ "$MY_IP" == "$GOOG" ]]
then
 echo 'No Change'
 exit 0
else
 echo 'What?'
 exit 1
fi
