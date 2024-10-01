#!/usr/bin/env python3

import json
import subprocess
import yaml
import logging
import sys
import os

# Configure logging
logging.basicConfig(
    filename='generate_volume_mappings.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)

def get_docker_volumes():
    """
    Retrieves all Docker volumes using 'docker volume ls' command.
    Returns a list of volume dictionaries.
    """
    try:
        cmd = ['docker', 'volume', 'ls', '--format', '{{ json . }}']
        result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
        volumes = [json.loads(line) for line in result.stdout.strip().split('\n') if line]
        logging.info(f"Retrieved {len(volumes)} volumes.")
        return volumes
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to list Docker volumes: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse Docker volumes output: {e}")
        sys.exit(1)

def get_volume_labels(volumes):
    """
    Batch inspects Docker volumes to retrieve their labels.
    Returns a dictionary mapping volume names to their labels.
    """
    volume_names = [v['Name'] for v in volumes]
    try:
        cmd = ['docker', 'volume', 'inspect'] + volume_names
        result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
        volumes_info = json.loads(result.stdout)
        volume_labels = {v['Name']: v.get('Labels', {}) for v in volumes_info}
        logging.info(f"Retrieved labels for {len(volumes_info)} volumes.")
        return volume_labels
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to inspect Docker volumes: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse Docker volumes inspect output: {e}")
        sys.exit(1)

def filter_named_volumes(volumes, volume_labels):
    """
    Filters out anonymous volumes based on the presence of the 'com.docker.volume.anonymous' label.
    Returns a list of named volume names.
    """
    named_volumes = []
    for v in volumes:
        name = v['Name']
        labels = volume_labels.get(name, {})
        if 'com.docker.volume.anonymous' not in labels:
            named_volumes.append(name)
        else:
            logging.debug(f"Excluding anonymous volume: {name}")
    logging.info(f"Filtered {len(named_volumes)} named volumes.")
    return named_volumes

def generate_volume_mappings(volumes):
    """
    Generates Docker Compose volume mappings for the given volumes.
    Returns a list of volume mapping strings.
    """
    mappings = []
    for name in volumes:
        # Map the volume to /mnt/source/<volume_name> in the container
        container_path = f"/mnt/source/{name}"
        mapping = f"      - {name}:{container_path}:ro"
        mappings.append(mapping)
        logging.debug(f"Generated mapping for volume: {name}")
    return mappings

def get_root_directories():
    """
    Defines the root directories to be backed up.
    Returns a list of volume mapping strings for these directories.
    """
    root_dirs = [
        '/root',
        '/home',
        '/etc',
        '/var/log',
        '/var/backups',
        '/opt'
    ]
    mappings = []
    for dir in root_dirs:
        if os.path.exists(dir):
            # Generate a unique container path
            container_path = dir.replace('/', '_').strip('_')
            container_path = f"/mnt/source/root/{container_path}"
            mapping = f"      - {dir}:{container_path}:ro"
            mappings.append(mapping)
            logging.debug(f"Added root directory mapping: {dir}")
        else:
            logging.warning(f"Root directory does not exist and will be skipped: {dir}")
    return mappings

def update_docker_compose(volume_mappings):
    """
    Updates the 'docker-compose.yml' file with the given volume mappings.
    """
    compose_file = 'docker-compose.yml'

    if not os.path.isfile(compose_file):
        logging.error(f"'{compose_file}' not found.")
        sys.exit(1)

    try:
        with open(compose_file, 'r') as f:
            compose = yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Failed to read '{compose_file}': {e}")
        sys.exit(1)

    services = compose.get('services', {})
    borgmatic_service = services.get('borgmatic', {})

    existing_volumes = borgmatic_service.get('volumes', [])
    # Preserve non-backup volumes (e.g., App Config volumes)
    app_config_volumes = [v for v in existing_volumes if v.strip().startswith('- ./') or v.strip().startswith('- /')]
    # Remove backup volume mappings
    new_volumes = app_config_volumes + volume_mappings

    borgmatic_service['volumes'] = new_volumes
    services['borgmatic'] = borgmatic_service
    compose['services'] = services

    # Ensure the volumes are declared under the 'volumes' key
    compose_volumes = compose.get('volumes', {})
    for mapping in volume_mappings:
        # Extract the volume name from the mapping
        volume_name = mapping.strip().split(':')[0].strip('- ')
        if volume_name.startswith('/'):
            # Skip host directories
            continue
        if volume_name not in compose_volumes:
            compose_volumes[volume_name] = {'external': True}
            logging.debug(f"Added volume to 'volumes' section: {volume_name}")
    compose['volumes'] = compose_volumes

    try:
        with open(compose_file, 'w') as f:
            yaml.dump(compose, f, default_flow_style=False)
        logging.info(f"Updated '{compose_file}' successfully.")
    except Exception as e:
        logging.error(f"Failed to write to '{compose_file}': {e}")
        sys.exit(1)

def main():
    logging.info("Starting volume mappings generation.")
    volumes_info = get_docker_volumes()
    volume_labels = get_volume_labels(volumes_info)
    named_volumes = filter_named_volumes(volumes_info, volume_labels)
    volume_mappings = generate_volume_mappings(named_volumes)
    root_mappings = get_root_directories()
    all_mappings = root_mappings + volume_mappings
    update_docker_compose(all_mappings)
    logging.info("Volume mappings generation completed successfully.")

if __name__ == "__main__":
    main()