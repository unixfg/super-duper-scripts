#!/usr/bin/env python3
import configparser
import os
import argparse
import requests
import time
import logging
import tempfile

def setup():
    # Set up argument parser and logging
    parser = argparse.ArgumentParser(description='Disk check and http ping utility')
    parser.add_argument('--verbose', action='store_true', help='Prints verbose output')
    parser.add_argument('--silent', action='store_true', help='Suppresses all output')
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    elif args.silent:
        logging.basicConfig(level=logging.CRITICAL)
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
    
    if 'DiskTestPath' not in config['DEFAULT']:
        logging.error('DiskTestPath is missing in the configuration file')
        exit(1)

    return args, config

def disk_test(directory):
    try:
        with tempfile.NamedTemporaryFile(dir=directory) as f:
            f.write(b'test')
            f.flush()
        logging.debug(f'Disk test passed on {directory}')
    except Exception as e:
        logging.error(f'Error: Disk test failed on {directory}, error: {str(e)}')
        exit(1)

def http_ping(http_ping_config):
    backoff_time = 1  # Start with a 1 second delay
    for i in range(http_ping_config['retries']):
        try:
            response = requests.get(f"{http_ping_config['url']}/{http_ping_config['api_key']}", timeout=http_ping_config['max_time'])
        except requests.exceptions.RequestException as e:
            if i == http_ping_config['retries'] - 1:
                logging.error(f'Error: All {http_ping_config["retries"]} HTTP ping attempts failed. Last error: {str(e)}')
                exit(1)
            logging.debug(f'HTTP ping failed (attempt {i+1}/{http_ping_config["retries"]}), retrying in {backoff_time} seconds... Error: {str(e)}')
            time.sleep(backoff_time)
            backoff_time *= 2  # Double the delay for the next attempt

# Run Setup
args, config = setup()

# Do Stuff
if config.getboolean('DEFAULT', 'DiskTest'):
    test_directory = config['DEFAULT']['DiskTestPath']
    logging.info('Performing disk test...')
    disk_test(test_directory)

http_ping_config = {
    'url': config['DEFAULT']['PingURL'],
    'api_key': config['DEFAULT']['APIKey'],
    'max_time': int(config['DEFAULT']['MaxTime']),
    'retries': int(config['DEFAULT']['Retries'])
}
logging.info('Sending HTTP pings...')
http_ping(http_ping_config)

logging.info('All tasks completed successfully')
