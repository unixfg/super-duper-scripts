import os
import imaplib
import email
import configparser
from email.header import decode_header
from tqdm import tqdm

# read the configuration file
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'))

# retrieve configuration
username = config.get('credentials', 'username')
password = config.get('credentials', 'password')
server = config.get('credentials', 'server')
output_file = config.get('settings', 'output', fallback='output.txt') # Fallback to 'output.txt' if no value is provided

# establish a connection
mail = imaplib.IMAP4_SSL(server)
# authenticate
mail.login(username, password)

# select the mailbox
mail.select("inbox")

# get uids
result, data = mail.uid('search', None, "ALL")
# list of uids
uid_list = data[0].split()

senders = []

# iterate over each email with a progress bar
for uid in tqdm(uid_list, desc='Processing emails', unit='email'):
    # fetch headers
    result, data = mail.uid('fetch', uid, '(BODY[HEADER.FIELDS (FROM)])')
    raw_email = data[0][1].decode("utf-8")
    email_message = email.message_from_string(raw_email)
    # decode the email address
    from_header = decode_header(email_message['From'])[0]
    if isinstance(from_header[0], bytes):
        # if it's a bytes type, decode to str
        from_header = from_header[0].decode(from_header[1])
    senders.append(from_header)

# unique senders
unique_senders = list(set(senders))

# write each sender to the output file
output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_file)
with open(output_path, 'w') as f:
    for sender in unique_senders:
        f.write(sender + '\n')

print(f'Unique senders saved to {output_path}')