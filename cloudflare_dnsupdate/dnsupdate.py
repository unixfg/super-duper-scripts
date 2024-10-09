#!/usr/bin/env python3
import requests
import os
import dns.resolver
import configparser
import argparse
import sys

def setup():
    """
    Parse arguments and read the configuration file.

    Returns:
    args: Namespace object containing the arguments.
    api_token: str containing the API key.
    dns_server: str containing the DNS server.
    ip_service_url: str containing the URL of the IP service.
    domains: list of dicts containing domain info.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--silent', help='If set, no output will be printed to the console', action='store_true')
    parser.add_argument('--verbose', help='If set, additional output will be printed to the console', action='store_true')
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.realpath(__file__))
    config_file = os.path.join(script_dir, 'config.ini')

    api_token, dns_server, ip_service_url, domains = get_config_params(config_file)

    return args, api_token, dns_server, ip_service_url, domains

def get_config_params(config_file):
    """
    Read and validate the configuration file.

    Parameters:
    config_file: str containing the path to the configuration file

    Returns:
    api_token: str containing the API token
    dns_server: str containing the DNS server
    ip_service_url: str containing the IP service URL
    domains: list of dicts containing domain info
    """
    config = configparser.ConfigParser()
    if not os.path.isfile(config_file):
        print(f"Configuration file {config_file} not found. Please make sure it exists and contains the necessary parameters.")
        sys.exit(1)
    config.read(config_file)

    try:
        api_token = config['DEFAULT']['API_TOKEN']
        dns_server = config['DEFAULT']['DNS_SERVER']
        ip_service_url = config['DEFAULT']['IP_SERVICE_URL']
    except KeyError as e:
        print(f"Missing {e} in DEFAULT section of configuration file.")
        sys.exit(1)

    domains = []
    for section in config.sections():
        if section != 'DEFAULT':
            domain_name = section
            try:
                zone_id = config[section]['ZONE_ID']
                subdomains = [s.strip() for s in config[section]['SUBDOMAINS'].split(',')]
                domains.append({'domain': domain_name, 'zone_id': zone_id, 'subdomains': subdomains})
            except KeyError as e:
                print(f"Missing {e} in {section} section of configuration file.")
                sys.exit(1)
    return api_token, dns_server, ip_service_url, domains

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
        response.raise_for_status()
        return response.text.strip()
    except requests.exceptions.RequestException as e:
        print(f"Error getting current IP: {e}")
        sys.exit(1)

def get_existing_ip(domain, subdomain, dns_server):
    """
    Get the existing IP address of the subdomain.

    Parameters:
    domain: str containing the domain name
    subdomain: str containing the subdomain name
    dns_server: str containing the DNS server

    Returns:
    str containing the existing IP address of the subdomain, or None if it doesn't exist
    """
    try:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [dns_server]
        answers = resolver.resolve(f'{subdomain}.{domain}', 'A')
        for rdata in answers:
            return rdata.address
        return None
    except dns.resolver.NXDOMAIN:
        # The domain does not exist
        return None
    except dns.resolver.NoAnswer:
        # The DNS response does not contain an answer to the question
        return None
    except dns.resolver.Timeout:
        print("Error: Timeout while resolving the domain.")
        sys.exit(1)
    except dns.resolver.NoNameservers:
        print("Error: No nameservers specified.")
        sys.exit(1)

def update_dns_record(api_token, zone_id, domain, subdomain, current_ip):
    """
    Call the Cloudflare API to update the DNS record.

    Parameters:
    api_token: str containing the API key
    zone_id: str containing the zone ID
    domain: str containing the domain
    subdomain: str containing the subdomain
    current_ip: str containing the current public IP address
    """
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    params = {"name": f"{subdomain}.{domain}", "type": "A"}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"Failed to fetch DNS record for {subdomain}.{domain}: {response.json()}")
        return

    dns_records = response.json()["result"]
    if not dns_records:
        print(f"No DNS record found for {subdomain}.{domain}. Creating a new one.")
        create_dns_record(api_token, zone_id, domain, subdomain, current_ip)
        return

    dns_record = dns_records[0]
    record_id = dns_record["id"]

    update_url = f"{url}/{record_id}"
    payload = {
        "type": "A",
        "name": f"{subdomain}.{domain}",
        "content": current_ip,
        "ttl": 1,
        "proxied": False
    }
    response = requests.put(update_url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"Failed to update DNS record for {subdomain}.{domain}: {response.json()}")
    else:
        print(f"Successfully updated DNS record for {subdomain}.{domain}.")

def create_dns_record(api_token, zone_id, domain, subdomain, current_ip):
    """
    Create a new DNS record via the Cloudflare API.

    Parameters:
    api_token: str containing the API key
    zone_id: str containing the zone ID
    domain: str containing the domain
    subdomain: str containing the subdomain
    current_ip: str containing the current public IP address
    """
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "type": "A",
        "name": f"{subdomain}.{domain}",
        "content": current_ip,
        "ttl": 1,
        "proxied": False
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"Failed to create DNS record for {subdomain}.{domain}: {response.json()}")
    else:
        print(f"Successfully created DNS record for {subdomain}.{domain}.")

def main():
    args, api_token, dns_server, ip_service_url, domains = setup()

    if args.verbose:
        print(f"API Token: {api_token}")
        print(f"DNS server: {dns_server}")
        print(f"IP service URL: {ip_service_url}")

    current_ip = get_current_ip(ip_service_url)
    if args.verbose:
        print(f"Current IP: {current_ip}")

    for domain_info in domains:
        domain = domain_info['domain']
        zone_id = domain_info['zone_id']
        subdomains = domain_info['subdomains']
        if args.verbose:
            print(f"Processing domain: {domain}")
            print(f"Zone ID: {zone_id}")
            print(f"Subdomains: {', '.join(subdomains)}")
        for subdomain in subdomains:
            if args.verbose:
                print(f"Processing subdomain: {subdomain}")
            existing_ip = get_existing_ip(domain, subdomain, dns_server)
            if args.verbose:
                print(f"Existing IP for {subdomain}.{domain}: {existing_ip}")
            if existing_ip is None:
                if not args.silent:
                    print(f"No existing DNS record for {subdomain}.{domain}. Creating one.")
                create_dns_record(api_token, zone_id, domain, subdomain, current_ip)
            elif current_ip != existing_ip:
                if not args.silent:
                    print(f"Updating DNS record for {subdomain}.{domain} to {current_ip}")
                update_dns_record(api_token, zone_id, domain, subdomain, current_ip)
            else:
                if not args.silent:
                    print(f"DNS record for {subdomain}.{domain} is up to date.")

if __name__ == "__main__":
    main()
