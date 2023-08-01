#!/usr/bin/env python3
import configparser
import os
import argparse
import requests
import time
import logging
import tempfile

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

# Read config file
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'))

# Get and validate config values
test_directory = config['DEFAULT']['DiskTestPath']
if config['DEFAULT'].getboolean('DiskTest'):
    if not os.path.exists(test_directory) or not os.access(test_directory, os.W_OK):
        logging.error(f'Test directory {test_directory} does not exist or is not writable')
        exit(1)

max_time = int(config['DEFAULT']['MaxTime'])
if max_time <= 0:
    logging.error('Max time must be a positive number')
    exit(1)

retries = int(config['DEFAULT']['Retries'])
if retries < 0:
    logging.error('Number of retries must be a non-negative integer')
    exit(1)

api_key = config['DEFAULT']['APIKey']
ping_url = config['DEFAULT']['PingURL']
try:
    requests.get(ping_url)
except requests.exceptions.MissingSchema:
    logging.error(f'Ping URL {ping_url} is not a valid URL')

def disk_test(directory):
    try:
        with tempfile.NamedTemporaryFile(dir=directory) as f:
            f.write(b'test')
            f.flush()
        logging.debug(f'Disk test passed on {directory}')
    except Exception as e:
        logging.error(f'Error: Disk test failed on {directory}, error: {str(e)}')
        exit(1)

def http_ping(ping_url, api_key, max_time, retries):
    for i in range(retries):
        try:
            response = requests.get(f'{ping_url}/{api_key}', timeout=max_time)
            if response.status_code == 200:
                logging.debug(f'HTTP ping successful (attempt {i+1}/{retries})')
                break
        except requests.exceptions.RequestException as e:
            if i == retries - 1:
                logging.error(f'Error: All {retries} HTTP ping attempts failed. Last error: {str(e)}')
                exit(1)
            logging.debug(f'HTTP ping failed (attempt {i+1}/{retries}), retrying... Error: {str(e)}')
            time.sleep(1)

if config['DEFAULT'].getboolean('DiskTest'):
    logging.info('Performing disk test...')
    disk_test(test_directory)

logging.info('Sending HTTP pings...')
http_ping(ping_url, api_key, max_time, retries)

logging.info('All tasks completed successfully')
