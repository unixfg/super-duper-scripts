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
    api_key: str containing the API key.
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

    api_key, domain, subdomain, dns_server, ip_service_url = get_config_params(config_file)

    return args, api_key, domain, subdomain, dns_server, ip_service_url

def get_config_params(config_file):
    """
    Read and validate the configuration file.

    Parameters:
    config_file: str containing the path to the configuration file

    Returns:
    api_key: str containing the API key
    domain: str containing the domain
    subdomain: str containing the subdomain
    dns_server: str containing the DNS server
    ip_service_url: str containing the URL of the IP service
    """
    config = configparser.ConfigParser()
    if not os.path.isfile(config_file):
        print(f"Configuration file {config_file} not found. Please make sure it exists and contains the necessary parameters.")
        sys.exit(1)
    config.read(config_file)
    return config['DEFAULT']['API_KEY'], config['DEFAULT']['DOMAIN'], config['DEFAULT']['SUBDOMAIN'], config['DEFAULT']['DNS_SERVER'], config['DEFAULT']['IP_SERVICE_URL']

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
    """
    Get the existing IP address of the subdomain.

    Parameters:
    domain: str containing the domain
    subdomain: str containing the subdomain
    dns_server: str containing the DNS server

    Returns:
    str containing the existing IP address of the subdomain
    """
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
    """
    Call the Gandi API to update the DNS record.

    Parameters:
    api_key: str containing the API key
    domain: str containing the domain
    subdomain: str containing the subdomain
    current_ip: str containing the current public IP address

    Returns:
    True if the DNS record was successfully updated, False otherwise
    """
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
    """
    Makes and prints comparisons then calls the update_dns_record function.
    """
    args, api_key, domain, subdomain, dns_server, ip_service_url = setup()

    if args.verbose:
        print(f"API key: {api_key}")
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
        if update_dns_record(api_key, domain, subdomain, current_ip):
            if not args.silent:
                print("DNS record successfully updated")
        else:
            print("Error updating DNS record")
    else:
        if not args.silent:
            print("DNS record is up to date")

if __name__ == "__main__":
    main()