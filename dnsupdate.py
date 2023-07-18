#!/usr/bin/env python3
import requests
import os
import dns.resolver

API_KEY = "XXXXXXXXXXXXXXXXXXXXXXXX"
DOMAIN = "domain.tld"
SUBDOMAIN = "example"
DNS_SERVER = "8.8.8.8"

def get_current_ip():
    response = requests.get('https://icanhazip.com/')
    return response.text.strip()

def get_existing_ip():
    resolver = dns.resolver.Resolver()
    resolver.nameservers = [DNS_SERVER]
    answers = resolver.resolve(f'{SUBDOMAIN}.{DOMAIN}')
    for rdata in answers:
        return rdata.address
    return None

def update_dns_record(current_ip):
    zone_records_href = f"https://dns.api.gandi.net/api/v5/domains/{DOMAIN}"
    headers = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}
    data = {
        "rrset_name": SUBDOMAIN,
        "rrset_type": "A",
        "rrset_ttl": 1200,
        "rrset_values": [current_ip]
    }
    response = requests.put(f"{zone_records_href}/{SUBDOMAIN}/A", headers=headers, json=data)
    return response.status_code == 200

def main():
    current_ip = get_current_ip()
    existing_ip = get_existing_ip()

    if current_ip != existing_ip:
        if update_dns_record(current_ip):
            print(f'Successfully updated DNS record of {SUBDOMAIN}.{DOMAIN} to {current_ip}')
        else:
            print(f'Failed to update DNS record of {SUBDOMAIN}.{DOMAIN}')
    elif current_ip == existing_ip:
        print('No Change')
    else:
        print('What?')

if __name__ == "__main__":
    main()