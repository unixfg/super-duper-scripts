#!/usr/bin/env python3

import json
import subprocess
import yaml
import logging
import sys
import os
import argparse
import fnmatch

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Generate Docker Compose volume mappings for backing up Docker volumes and root directories.'
    )
    parser.add_argument(
        '-o', '--output',
        default='docker-compose.override.yml',
        help='Output file name for the generated Docker Compose file (default: docker-compose.override.yml).'
    )
    parser.add_argument(
        '-s', '--service',
        default='borgmatic',
        help='Name of the service in Docker Compose to which volumes will be added (default: borgmatic).'
    )
    parser.add_argument(
        '-r', '--root-dirs',
        action='append',
        help='Root directories to include in backups (can be specified multiple times).'
    )
    parser.add_argument(
        '-e', '--exclude-volumes',
        action='append',
        help='Volumes to exclude from backups (can be specified multiple times).'
    )
    parser.add_argument(
        '-i', '--include-volumes',
        action='append',
        help='Volumes to include in backups (supports glob patterns, can be specified multiple times).'
    )
    parser.add_argument(
        '--include-service-volumes',
        action='store_true',
        help='Include volumes used by the specified service.'
    )
    parser.add_argument(
        '--separate-declarations',
        action='store_true',
        help='Generate volume declarations in a separate file (volumes-declare.yml).'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging.'
    )
    return parser.parse_args()

def configure_logging(verbose):
    logging.basicConfig(
        filename='generate_volume_mappings.log',
        level=logging.DEBUG if verbose else logging.INFO,
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

def get_service_volumes(service_name):
    """
    Retrieves the list of volumes used by the specified service from the docker-compose.yml file.
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
    service = services.get(service_name, {})
    volumes = service.get('volumes', [])
    service_volumes = []

    for v in volumes:
        # Extract the volume name from the mapping
        if isinstance(v, str):
            volume_name = v.split(':')[0]
            if not volume_name.startswith('./') and not volume_name.startswith('/'):
                service_volumes.append(volume_name)
                logging.debug(f"Service '{service_name}' uses volume: {volume_name}")
        elif isinstance(v, dict):
            # Handle long syntax
            volume_name = v.get('source')
            if volume_name and not volume_name.startswith('./') and not volume_name.startswith('/'):
                service_volumes.append(volume_name)
                logging.debug(f"Service '{service_name}' uses volume: {volume_name}")

    return service_volumes

def filter_named_volumes(volumes, volume_labels, exclude_volumes, include_patterns, service_volumes, include_service_volumes):
    """
    Filters out anonymous volumes and applies include/exclude filters.
    Returns a list of volume names to include.
    """
    named_volumes = []
    for v in volumes:
        name = v['Name']
        labels = volume_labels.get(name, {})
        if 'com.docker.volume.anonymous' in labels:
            logging.debug(f"Excluding anonymous volume: {name}")
            continue

        if not include_service_volumes and name in service_volumes:
            logging.debug(f"Excluding volume used by service '{args.service}': {name}")
            continue

        if exclude_volumes and name in exclude_volumes:
            logging.debug(f"Excluding volume (by exclude list): {name}")
            continue

        if include_patterns:
            matched = any(fnmatch.fnmatch(name, pattern) for pattern in include_patterns)
            if not matched:
                logging.debug(f"Excluding volume (by include patterns): {name}")
                continue

        named_volumes.append(name)

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

def get_root_directories(root_dirs):
    """
    Returns a list of volume mapping strings for the specified root directories.
    """
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

def generate_compose_file(service_name, volume_mappings, volume_declarations, output_file):
    """
    Generates a Docker Compose file containing the volume mappings and declarations.
    """
    compose_data = {
        'services': {
            service_name: {
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

def generate_volume_declarations(volume_declarations, output_file):
    """
    Generates a Docker Compose file containing the volume declarations.
    """
    compose_data = {
        'volumes': volume_declarations
    }
    try:
        with open(output_file, 'w') as f:
            yaml.dump(compose_data, f, default_flow_style=False)
        logging.info(f"Generated volume declarations compose file: {output_file}")
    except Exception as e:
        logging.error(f"Failed to write to '{output_file}': {e}")
        sys.exit(1)

def main():
    global args  # Make args accessible in filter_named_volumes()
    args = parse_arguments()
    configure_logging(args.verbose)
    logging.info("Starting volume mappings generation.")

    # Default root directories if not provided
    default_root_dirs = [
        '/root',
        '/home',
        '/etc',
        '/var/log',
        '/var/backups',
        '/opt'
    ]
    root_dirs = args.root_dirs if args.root_dirs else default_root_dirs

    # Get volumes used by the specified service
    service_volumes = get_service_volumes(args.service)
    if args.verbose:
        logging.debug(f"Service '{args.service}' uses volumes: {service_volumes}")

    volumes_info = get_docker_volumes()
    volume_labels = get_volume_labels(volumes_info)
    named_volumes = filter_named_volumes(
        volumes_info,
        volume_labels,
        exclude_volumes=args.exclude_volumes,
        include_patterns=args.include_volumes,
        service_volumes=service_volumes,
        include_service_volumes=args.include_service_volumes
    )
    volume_mappings = generate_volume_mappings(named_volumes)
    root_mappings = get_root_directories(root_dirs)

    all_mappings = root_mappings + volume_mappings

    # Prepare volume declarations for named volumes
    volume_declarations = {name: {'external': True} for name in named_volumes}

    if args.separate_declarations:
        # Generate separate files
        generate_compose_file(args.service, all_mappings, {}, args.output)
        generate_volume_declarations(volume_declarations, 'volumes-declare.yml')
    else:
        # Include declarations in the same file
        generate_compose_file(args.service, all_mappings, volume_declarations, args.output)

    logging.info("Volume mappings generation completed successfully.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)
        
