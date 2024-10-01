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
        volume_labels = {v['Name']: v.get('Labels') or {} for v in volumes_info}
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
    Generates volume mappings for the given volumes.
    Returns a list of volume mapping strings.
    """
    mappings = []
    for name in volumes:
        # Map the volume to /mnt/source/<volume_name> in the container
        container_path = f"/mnt/source/{name}"
        mapping = f"{name}:{container_path}:ro"
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
            mapping = f"{dir}:{container_path}:ro"
            mappings.append(mapping)
            logging.debug(f"Added root directory mapping: {dir}")
        else:
            logging.warning(f"Root directory does not exist and will be skipped: {dir}")
    return mappings

def generate_compose_file(volume_mappings, volume_declarations, output_file='volumes-compose.yml'):
    """
    Generates a Docker Compose file containing the volume mappings and declarations.
    """
    compose_data = {
        'services': {
            'borgmatic': {
                'volumes': volume_mappings
            }
        },
        'volumes': volume_declarations
    }
    try:
        with open(output_file, 'w') as f:
            yaml.dump(compose_data, f, default_flow_style=False)
        logging.info(f"Generated volume mappings compose file: {output_file}")
    except Exception as e:
        logging.error(f"Failed to write to '{output_file}': {e}")
        sys.exit(1)

def main():
    logging.info("Starting volume mappings generation.")
    volumes_info = get_docker_volumes()
    volume_labels = get_volume_labels(volumes_info)
    named_volumes = filter_named_volumes(volumes_info, volume_labels)
    volume_mappings = generate_volume_mappings(named_volumes)
    root_mappings = get_root_directories()

    all_mappings = root_mappings + volume_mappings

    # Prepare volume declarations for named volumes
    volume_declarations = {name: {'external': True} for name in named_volumes}

    generate_compose_file(all_mappings, volume_declarations)
    logging.info("Volume mappings generation completed successfully.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)