#!/usr/bin/env python3
import requests
import os
import dns.resolver
import configparser
import argparse
import sys

def get_config_params(config_file):
    config = configparser.ConfigParser()
    if not os.path.isfile(config_file):
        print(f"Configuration file {config_file} not found. Please make sure it exists and contains the necessary parameters.")
        sys.exit(1)
    config.read(config_file)
    return config['DEFAULT']['API_KEY'], config['DEFAULT']['DOMAIN'], config['DEFAULT']['SUBDOMAIN'], config['DEFAULT']['DNS_SERVER'], config['DEFAULT']['IP_SERVICE_URL']

def get_current_ip(ip_service_url):
    try:
        response = requests.get(ip_service_url)
        return response.text.strip()
    except requests.exceptions.RequestException as e:
        print(f"Error getting current IP: {e}")
        sys.exit(1)

def get_existing_ip(domain, subdomain, dns_server):
    try:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [dns_server]
        answers = resolver.resolve(f'{subdomain}.{domain}')
        for rdata in answers:
            return rdata.address
        return None
    except dns.resolver.NXDOMAIN:
        print(f"Error: The domain {subdomain}.{domain} does not exist.")
        sys.exit(1)
    except dns.resolver.Timeout:
        print("Error: Timeout while resolving the domain.")
        sys.exit(1)
    except dns.resolver.NoNameservers:
        print("Error: No nameservers specified.")
        sys.exit(1)

def update_dns_record(api_key, domain, subdomain, current_ip):
    zone_records_href = f"https://dns.api.gandi.net/api/v5/domains/{domain}"
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    data = {
        "rrset_name": subdomain,
        "rrset_type": "A",
        "rrset_ttl": 1200,
        "rrset_values": [current_ip]
    }
    try:
        response = requests.put(f"{zone_records_href}/{subdomain}/A", headers=headers, json=data)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Error updating DNS record: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--silent', help='If set, no output will be printed to the console', action='store_true')
    parser.add_argument('--verbose', help='If set, additional output will be printed to the console', action='store_true')
    args = parser.parse_args()

    # Define the path to the config file
    script_dir = os.path.dirname(os.path.realpath(__file__))
    config_file = os.path.join(script_dir, 'config.ini')

    api_key, domain, subdomain, dns_server, ip_service_url = get_config_params(config_file)

    current_ip = get_current_ip(ip_service_url)
    if args.verbose: print(f'Current IP: {current_ip}')

    existing_ip = get_existing_ip(domain, subdomain, dns_server)
    if args.verbose: print(f'Existing IP: {existing_ip}')

    if current_ip != existing_ip:
        if update_dns_record(api_key, domain, subdomain, current_ip):
            if not args.silent: print(f'Successfully updated DNS record of {subdomain}.{domain} to {current_ip}')
        else:
            if not args.silent: print(f'Failed to update DNS record of {subdomain}.{domain}')
    elif current_ip == existing_ip:
        if args.verbose: print('IP address has not changed')
    else:
        print('Unknown error')

if __name__ == "__main__":
    main()
