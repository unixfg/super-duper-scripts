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
    Parse arguments and set up logging.
    Read and validate the configuration file.
    Validate 'APIKey' and 'PingURL'.
    Validate 'MaxTime' and 'Retries', including converting them to integers and handling potential exceptions.
    Form and validate the full URL.
    Create the http_ping_config dictionary.
    
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
        logging.critical(f'Configuration file {config_path} does not exist or is not readable')
        exit(1)

    config = configparser.ConfigParser()
    config.read(config_path)

    # Get and validate config values
    api_key = config['DEFAULT']['APIKey']
    if not api_key:
        logging.critical('API key is missing in the configuration file')
        exit(1)

    ping_url = config['DEFAULT']['PingURL']
    if not ping_url:
        logging.critical('Ping URL is missing in the configuration file')
        exit(1)

    # Set default values
    default_max_time = 30
    default_retries = 3

    max_time = config['DEFAULT']['MaxTime']
    if not max_time:
        logging.error('MaxTime is missing in the configuration file, using default value.')
        max_time = default_max_time
    else:
        try:
            max_time = int(max_time)
        except ValueError:
            logging.error('MaxTime is not an integer, using default value.')
            max_time = default_max_time

    retries = config['DEFAULT']['Retries']
    if not retries:
        logging.error('Retries is missing in the configuration file, using default value.')
        retries = default_retries
    else:
        try:
            retries = int(retries)
        except ValueError:
            logging.error('Retries is not an integer, using default value.')
            retries = default_retries

    # Create the URL from the config values and validate it
    full_url = f"{ping_url}/{api_key}"
    try:
        result = urllib.parse.urlparse(full_url)
        if all([result.scheme, result.netloc]):
            logging.debug(f'Full URL is well-formed: {full_url}')
        else:
            logging.critical(f'Full URL is not well-formed: {full_url}')
            exit(1)
    except Exception as e:
        logging.critical(f'Error parsing URL: {full_url}, error: {str(e)}')
        exit(1)

    # Create the config dictionary that will be passed to the HTTP ping function
    http_ping_config = {
    'url': full_url,
    'max_time': max_time,
    'retries': retries
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
            logging.info(f'HTTP request successful, status code: {response.status_code}')
            break  # If the request was successful, break the loop
        except requests.exceptions.RequestException as e:
            if i == http_ping_config['retries'] - 1:
                logging.error(f'Error: All {http_ping_config["retries"]} HTTP ping attempts failed. Last error: {str(e)}')
                exit(1)
            logging.debug(f'HTTP ping failed (attempt {i+1}/{http_ping_config["retries"]}), retrying in {backoff_time} seconds... Error: {str(e)}')
            logging.error(f'HTTP request failed, status code: {response.status_code}, error: {str(e)}')
            time.sleep(backoff_time)
            backoff_time *= 1.5  # Increase the delay for the next attempt

# Run Setup
args, http_ping_config = setup()

# Do Stuff
logging.info('Sending HTTP ping...')
http_ping(http_ping_config)

logging.info('Completed successfully')