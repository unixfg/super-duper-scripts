import os
import imaplib
import email
import configparser
from email.header import decode_header
from tqdm import tqdm
import argparse
import time
from datetime import datetime, timedelta

# Handle command line arguments
parser = argparse.ArgumentParser(description='Fetch unique senders from an email account.')
parser.add_argument('--max-age', type=int, default=90, help='Maximum age of messages to consider, in days (default: 90 days)')
parser.add_argument('--verbose', action='store_true', help='Increase output verbosity')
parser.add_argument('--silent', action='store_true', help='Silence progress bar and output')
args = parser.parse_args()

# read the configuration file
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'))

# retrieve configuration
username = config.get('credentials', 'username')
password = config.get('credentials', 'password')
server = config.get('credentials', 'server')
output_file = config.get('settings', 'output', fallback='output.txt')

# establish a connection
mail = imaplib.IMAP4_SSL(server)
# authenticate
mail.login(username, password)

# select the mailbox
mail.select("inbox")

# get uids
result, data = mail.uid('search', None, f'(SINCE {datetime.now() - timedelta(days=args.max_age):%d-%b-%Y})')  # search for emails no older than max-age
# list of uids
uid_list = data[0].split()

senders = []

# iterate over each email with a progress bar (or without if silent)
for uid in tqdm(uid_list, desc='Processing emails', unit='email', disable=args.silent):
    # fetch headers
    result, data = mail.uid('fetch', uid, '(BODY[HEADER.FIELDS (FROM DATE)])')
    raw_email = data[0][1].decode("utf-8")
    email_message = email.message_from_string(raw_email)
    # decode the email address
    from_header = decode_header(email_message['From'])[0]
    if isinstance(from_header[0], bytes):
        # if it's a bytes type, decode to str
        sender = from_header[0].decode(from_header[1] if from_header[1] is not None else 'utf-8')  # default to 'utf-8' if encoding is None
    else:
        sender = from_header[0]  # If it's already a string, no need to decode
    senders.append(sender)

# unique senders
unique_senders = list(set(senders))

# write each sender to the output file
output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_file)
with open(output_path, 'w') as f:
    for sender in unique_senders:
        if args.verbose:
            print(f'Writing: {sender}')
        f.write(sender + '\n')

if not args.silent:
    print(f'Unique senders saved to {output_path}')