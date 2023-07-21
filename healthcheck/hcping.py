#!/usr/bin/env python3
import configparser
import os
import argparse
import requests
import time

# Set up argument parser
parser = argparse.ArgumentParser(description='Disk check and http ping utility')
parser.add_argument('--help', action='store_true', help='Prints this help text')
parser.add_argument('--verbose', action='store_true', help='Prints verbose output')
parser.add_argument('--silent', action='store_true', help='Suppresses all output')
args = parser.parse_args()

# Check for --help flag
if args.help:
    parser.print_help()
    exit(0)

# Read config file
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'))

# Get config values
test_path = config['DEFAULT']['DiskTestPath']
max_time = int(config['DEFAULT']['MaxTime'])
retries = int(config['DEFAULT']['Retries'])
api_key = config['DEFAULT']['APIKey']
ping_url = config['DEFAULT']['PingURL']

# Disk test
if not args.silent:
    print('Performing disk test...')
if config['DEFAULT'].getboolean('DiskTest'):
    try:
        with open(test_path, 'w') as f:
            f.write('test')
        os.remove(test_path)
        if args.verbose:
            print(f'Disk test passed on {test_path}')
    except:
        print(f'Error: Disk test failed on {test_path}')
        exit(1)

# HTTP ping
if not args.silent:
    print('Sending HTTP pings...')
for i in range(retries):
    try:
        response = requests.get(f'{ping_url}/{api_key}', timeout=max_time)
        if response.status_code == 200:
            if args.verbose:
                print(f'HTTP ping successful (attempt {i+1}/{retries})')
            break
    except:
        if i == retries - 1:
            print(f'Error: All {retries} HTTP ping attempts failed')
            exit(1)
        if args.verbose:
            print(f'HTTP ping failed (attempt {i+1}/{retries}), retrying...')
        time.sleep(1)

if not args.silent:
    print('All tasks completed successfully')