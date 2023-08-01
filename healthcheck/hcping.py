#!/usr/bin/env python3
import configparser
import os
import argparse
import requests
import time
import logging
import tempfile
import urllib.parse

def setup():
    """
    Reads and validates the configuration file, sets up logging, and returns the config dictionary
    
    Parameters:
    None

    Returns:
    args: argparse.Namespace
    http_ping_config: dict containing the configuration values for the HTTP ping
    """

    # Set up argument parser and logging
    parser = argparse.ArgumentParser(description='HTTP ping utility')
    parser.add_argument('--verbose', action='store_true', help='Prints verbose output')
    parser.add_argument('--silent', action='store_true', help='Suppresses all output')
    args = parser.parse_args()

    if args.silent:
        logging.basicConfig(level=logging.CRITICAL)
    elif args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Read and validate config file
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
    if not os.path.exists(config_path) or not os.access(config_path, os.R_OK):
        logging.error(f'Configuration file {config_path} does not exist or is not readable')
        exit(1)

    config = configparser.ConfigParser()
    config.read(config_path)

    # Get and validate config values
    api_key = config['DEFAULT']['APIKey']
    if not api_key:
        logging.error('API key is missing in the configuration file')
        exit(1)
    ping_url = config['DEFAULT']['PingURL']
    if not ping_url:
        logging.error('Ping URL is missing in the configuration file')
        exit(1)

    # Create the URL from the config values and validate it
    full_url = f"{ping_url}/{api_key}"
    try:
        result = urllib.parse.urlparse(full_url)
        if all([result.scheme, result.netloc]):
            logging.debug(f'Full URL is well-formed: {full_url}')
        else:
            logging.error(f'Full URL is not well-formed: {full_url}')
            exit(1)
    except Exception as e:
        logging.error(f'Error parsing URL: {full_url}, error: {str(e)}')
        exit(1)

    # Create the config dictionary that will be passed to the HTTP ping function
    http_ping_config = {
    'url': config['DEFAULT']['FullURL'],
    'max_time': int(config['DEFAULT']['MaxTime']),
    'retries': int(config['DEFAULT']['Retries'])
    }

    return args, http_ping_config

def http_ping(http_ping_config):
    """
    Sends an HTTP ping to the specified URL
    
    Parameters:
    http_ping_config: dict containing the configuration values for the HTTP ping

    Returns:
    None
    """

    backoff_time = 2  # Start with a 2 second delay
    for i in range(http_ping_config['retries']):
        try:
            response = requests.get(f"{http_ping_config['url']}", timeout=http_ping_config['max_time'])
            response.raise_for_status()  # Check if the request was successful
            break  # If the request was successful, break the loop
        except requests.exceptions.RequestException as e:
            if i == http_ping_config['retries'] - 1:
                logging.error(f'Error: All {http_ping_config["retries"]} HTTP ping attempts failed. Last error: {str(e)}')
                exit(1)
            logging.debug(f'HTTP ping failed (attempt {i+1}/{http_ping_config["retries"]}), retrying in {backoff_time} seconds... Error: {str(e)}')
            time.sleep(backoff_time)
            backoff_time *= 1.5  # Increase the delay for the next attempt

# Run Setup
args, http_ping_config = setup()

# Do Stuff
logging.info('Sending HTTP ping...')
http_ping(http_ping_config)

logging.info('Completed successfully')