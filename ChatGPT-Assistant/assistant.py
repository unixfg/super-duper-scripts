#!/usr/bin/env python3

import json
import os
import requests

# Functions

def create_headers(config):
    api_key = config["api_key"]
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
        'OpenAI-Beta': 'assistants=v1'
    }

def get_main_assistant_id(headers, config):
    """
    Checks for the existence of the 'Main Assistant' and returns its ID.
    If it does not exist, it creates the 'Main Assistant' and returns the new ID.

    :param headers: The headers to use for the API request.
    :param config: The configuration dictionary.
    :return: The ID of the main assistant.
    """
    assistants = list_assistants(headers, config)
    
    # Check if 'Main Assistant' exists
    for assistant in assistants['data']:
        if assistant['name'] == config['assistant_configuration']['name']:
            return assistant['id']

    # 'Main Assistant' does not exist, create a new one
    assistant = create_assistant(headers, config)
    return assistant['id']

def parse_assistant_messages(response):
    """
    Parses the messages received in the response from the assistant.
    
    :param response: The JSON response from the API.
    :return: A tuple containing two lists, one for chat messages and one for actions.
    """
    # Initialize empty lists to hold the parsed messages
    chat_messages = []
    action_messages = []

    # The data key contains a list of messages
    messages = response.get('data', [])

    # Iterate over the messages and process them based on their 'role'
    for msg in messages:
        # Each 'content' is a list of content items, we only consider the first one for simplicity
        if msg['content'] and 'text' in msg['content'][0]:
            message_text = msg['content'][0]['text']['value']
            if msg['role'] == 'assistant':
                # For chat responses from the assistant
                chat_messages.append(message_text)
            else:
                # For non-chat messages, such as commands or structured data
                action_messages.append(message_text)

    return chat_messages, action_messages

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def save_thread_id(assistant_id, thread_id):
    threads = {}
    if os.path.exists('threads.json'):
        with open('threads.json', 'r') as f:
            threads = json.load(f)
    if assistant_id not in threads:
        threads[assistant_id] = []
    threads[assistant_id].append(thread_id)
    with open('threads.json', 'w') as f:
        json.dump(threads, f, indent=4)

def get_threads(assistant_id):
    if not os.path.exists('threads.json'):
        return []
    with open('threads.json', 'r') as f:
        threads = json.load(f)
    return threads.get(assistant_id, [])

def create_assistant(headers, config):
    assistant_details = config['assistant_configuration']
    create_assistant_url = f"{config['api_url']}assistants"
    response = requests.post(create_assistant_url, headers=headers, json=assistant_details)
    response.raise_for_status()
    return response.json()

def get_existing_thread_id():
    try:
        with open('threads.json', 'r') as file:
            threads_data = json.load(file)
            return threads_data.get('thread_id')
    except FileNotFoundError:
        return None
    
def run_existing_thread(assistant_id, thread_id, message, headers, config):
    # First, send the message to the existing thread
    send_message_response = send_message_to_assistant(thread_id, message, headers, config)

    # Then, run the thread
    run_thread_url = f"{config['api_url']}threads/{thread_id}/runs"
    run_data = {
        "assistant_id": assistant_id
    }
    run_response = requests.post(run_thread_url, headers=headers, json=run_data)
    run_response.raise_for_status()

    return run_response.json()

def create_thread_and_run(assistant_id, message, headers, config):
    url = f"{config['api_url']}threads/runs"
    data = {
        "assistant_id": assistant_id,
        "thread": {
            "messages": [
                {"role": "user", "content": message}
            ]
        }
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    thread_run_response = response.json()

    # Save the new thread ID to threads.json
    with open('threads.json', 'w') as file:
        json.dump({"thread_id": thread_run_response['thread_id']}, file)

    return thread_run_response

def send_message_to_assistant(thread_id, message, headers, config):
    send_message_url = f"{config['api_url']}threads/{thread_id}/messages"
    message_data = {
        "role": "user",
        "content": message
    }
    response = requests.post(send_message_url, headers=headers, json=message_data)
    response.raise_for_status()
    return response.json()

def list_assistants(headers, config):
    try:
        list_assistants_url = f"{config['api_url']}assistants"
        response = requests.get(list_assistants_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            print("Error: Unauthorized access. Check your API key.")
        else:
            print(f"HTTP Error occurred: {e}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def main():
    # Load configuration
    with open('config.json') as config_file:
        config = json.load(config_file)

    # Create headers
    headers = create_headers(config['api_key'])

    # Get the main assistant's ID
    assistant_id = get_main_assistant_id(headers, config)

    # Prompt for user input
    message = input("Enter your message: ")

    # Check for existing thread
    existing_thread_id = get_existing_thread_id()

    if existing_thread_id:
        # Run existing thread with the new message
        response = run_existing_thread(assistant_id, existing_thread_id, message, headers, config)
    else:
        # Create thread and run with the new message
        response = create_thread_and_run(assistant_id, message, headers, config)

    # Process and display the response
    print(response)

# Other functions (create_headers, get_main_assistant_id, get_existing_thread_id, run_existing_thread, create_thread_and_run) go here

if __name__ == "__main__":
    main()