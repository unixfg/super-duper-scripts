#!/bin/bash
if
 SET_IP=$(dig @1.1.1.1 +short subdomain.example.com)
then :
else
 echo 'dig failed'
 exit 1
fi

if
 MY_IP=$(curl -s https://icanhazip.com)
then :
else
  echo 'stun failed'
  exit 1
fi

if [ "$SET_IP" = "$MY_IP" ]
then
 exit 0
else

 APIKEY="APIKEYGOESHERE"
 DOMAIN="example.com"
 SUBDOMAIN="subdomain"
 echo "We Are IP $MY_IP"
 echo "DNS Record is $SET_IP"

 if
  CURRENT_ZONE_HREF=$(curl -s -H "X-Api-Key: $APIKEY" https://dns.api.gandi.net/api/v5/domains/$DOMAIN | jq -r '.zone_records_href')
 then echo 'Got JSON'
  else echo 'API JSON Failed'
  exit 1
 fi

 if
 curl -D- -X PUT -H "Content-Type: application/json" \
        -H "X-Api-Key: $APIKEY" \
        -d "{\"rrset_name\": \"$SUBDOMAIN\",
             \"rrset_type\": \"A\",
             \"rrset_ttl\": 1200,
             \"rrset_values\": [\"$MY_IP\"]}" \
        $CURRENT_ZONE_HREF/$SUBDOMAIN/A
 then echo "Set Record fileserver IN A $MY_IP"
  else
   echo 'PUT failed'
   exit 1
 fi
fi
