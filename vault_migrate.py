import openpyxl
import subprocess
import os
import json

# Prompt for the Excel file and category
file_path = input("Enter the path to the Excel file: ")
category = input("Enter the category: ")

# Load workbook
wb = openpyxl.load_workbook(file_path)
sheet = wb.active

# Skip the header row
rows = sheet.iter_rows(min_row=2, values_only=True)

# Prepare kv put commands and kv metadata put commands
commands = []
metadata_commands = []
for row in rows:
    # Unpack row values
    resource_name, user_account, password, last_access_time, description, dns_name, department, location, os_type, resource, notes, system_name, api_key = row

    # Full path in Vault
    full_path = f'secret/{category}/{resource_name}'

    # Prepare kv put command
    kv_pairs = [f'{user_account}={password}']
    
    # If there's an API key and it's not "null", prepare it
    if api_key and api_key.lower() != "null":
        kv_pairs.append(f'api_key={api_key}')

    command = ['vault', 'kv', 'put', full_path] + kv_pairs
    commands.append(command)

    # Prepare metadata command if there's a description
    if description:
        metadata_command = ['vault', 'kv', 'metadata', 'put', full_path, '-custom-metadata', f'description={description}']
        metadata_commands.append(metadata_command)

# Print commands for verification
print("The following commands will be run:")
for command in commands:
    # Replace password and api keys with asterisks for printing
    print_command = command.copy()
    for i in range(4, len(print_command)):  # Start from 4 to skip 'vault', 'kv', 'put' and the path
        print_command[i] = print_command[i].split('=')[0] + '=********'  # Replace password or api key
    print(' '.join(print_command))

# Print metadata commands for verification
print("The following metadata commands will be run:")
for command in metadata_commands:
    # Replace description with asterisks for printing
    print_command = command.copy()
    print_command[-1] = print_command[-1].split('=')[0] + '=********'  # Replace description
    print(' '.join(print_command))

# Ask for confirmation
confirmation = input('Are you sure you want to run these commands? (yes/no) ')
if confirmation.lower() == 'yes':
    # Run commands
    for command in commands:
        subprocess.run(command, check=True)

    # Run metadata commands
    for command in metadata_commands:
        subprocess.run(command, check=True)
else:
    print('Operation cancelled.')