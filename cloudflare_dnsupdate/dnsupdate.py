#!/usr/bin/env python3
import requests
import os
import dns.resolver
import configparser
import argparse
import json
import sys

def setup():
    """
    Parse arguments and read the configuration file.

    Returns:
    args: Namespace object containing the arguments.
    api_token: str containing the API key.
    zone_id: str containing the zone ID.
    domain: str containing the domain.
    subdomain: str containing the subdomain.
    dns_server: str containing the DNS server.
    ip_service_url: str containing the URL of the IP service.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--silent', help='If set, no output will be printed to the console', action='store_true')
    parser.add_argument('--verbose', help='If set, additional output will be printed to the console', action='store_true')
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.realpath(__file__))
    config_file = os.path.join(script_dir, 'config.ini')

    api_token, zone_id, domain, subdomain, dns_server, ip_service_url = get_config_params(config_file)

    return args, api_token, zone_id, domain, subdomain, dns_server, ip_service_url

def get_config_params(config_file):
    """
    Called by setup()
    Read and validate the configuration file.

    Parameters:
    config_file: str containing the path to the configuration file

    Returns:
    config: ConfigParser object containing the configuration file
    """
    config = configparser.ConfigParser()
    if not os.path.isfile(config_file):
        print(f"Configuration file {config_file} not found. Please make sure it exists and contains the necessary parameters.")
        sys.exit(1)
    config.read(config_file)
    return config['Cloudflare']['API_TOKEN'], config['Cloudflare']['ZONE_ID'], config['DEFAULT']['DOMAIN'], config['DEFAULT']['SUBDOMAIN'], config['DEFAULT']['DNS_SERVER'], config['DEFAULT']['IP_SERVICE_URL']

def get_current_ip(ip_service_url):
    """
    Get the current public IP address.

    Parameters:
    ip_service_url: str containing the URL of the IP service
    
    Returns:
    str containing the current public IP address
    """
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

def update_dns_record(api_token, zone_id, domain, subdomain, current_ip):
    """
    Call the CloudFlare API to update the DNS record.

    Parameters:
    api_token: str containing the API key
    zone_id: str containing the zone ID
    domain: str containing the domain
    subdomain: str containing the subdomain
    current_ip: str containing the current public IP address

    Returns:
    True if the DNS record was successfully updated, False otherwise
    """
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    params = {"name": f"{subdomain}.{domain}"}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"Failed to fetch DNS record: {response.json()}")
        return

    dns_record = response.json()["result"][0]
    record_id = dns_record["id"]

    update_url = f"{url}/{record_id}"
    payload = {
        "type": "A",
        "name": subdomain,
        "content": current_ip
    }
    response = requests.put(update_url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"Failed to update DNS record: {response.json()}")
    else:
        print("Successfully updated DNS record.")

def main():
    args, api_token, zone_id, domain, subdomain, dns_server, ip_service_url = setup()

    if args.verbose:
        print(f"API Token: {api_token}")
        print(f"Zone ID: {zone_id}")
        print(f"Domain: {domain}")
        print(f"Subdomain: {subdomain}")
        print(f"DNS server: {dns_server}")
        print(f"IP service URL: {ip_service_url}")

    current_ip = get_current_ip(ip_service_url)
    if args.verbose:
        print(f"Current IP: {current_ip}")

    existing_ip = get_existing_ip(domain, subdomain, dns_server)
    if args.verbose:
        print(f"Existing IP: {existing_ip}")

    if current_ip != existing_ip:
        if not args.silent:
            print(f"Updating DNS record for {subdomain}.{domain} to {current_ip}")
        update_dns_record(api_token, zone_id, domain, subdomain, current_ip)
    else:
        if not args.silent:
            print("DNS record is up to date")

if __name__ == "__main__":
    main()
