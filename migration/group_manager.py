import os
import time
import logging
import gitlab
from typing import List, Dict

def get_group_details(gl: gitlab.Gitlab, group_path: str) -> Dict[str, str]:
    """
    Get group name and path from source using group path
    
    Args:
        gl: Source GitLab instance
        group_path: Full path to the group
    """
    try:
        group = gl.groups.get(group_path)
        return {
            'name': group.name,
            'path': group.path
        }
    except gitlab.exceptions.GitlabGetError as e:
        logging.error(f'Failed to get group details for path {group_path}: {e}')
        raise

def export_group(gl: gitlab.Gitlab, group_id: int) -> List[Dict]:
    logging.info(f'Starting export for group {group_id}')
    group = gl.groups.get(group_id)
    export = group.exports.create()
    logging.info(f'Export created for group {group_id}, waiting for it to finish')

    # Wait for the export to finish before downloading
    time.sleep(10)

    export_path = 'exports/group'
    os.makedirs(export_path, exist_ok=True)

    with open(os.path.join(export_path, f'group-{group_id}-export.tgz'), 'wb') as f:
        export.download(streamed=True, action=f.write)
    logging.info(f'Export for group {group_id} downloaded successfully')

def import_group(dest_gl: gitlab.Gitlab, source_gl: gitlab.Gitlab, group_path: str, 
                parent_id: int = None, name: str = None, path: str = None):
    """
    Import group with optional new name/path or use source group values
    
    Args:
        dest_gl: Destination GitLab instance
        source_gl: Source GitLab instance 
        group_path: Source group path
        parent_id: Destination parent group ID
        name: New group name (optional)
        path: New group path (optional)
    """
    if not name or not path:
        source_details = get_group_details(source_gl, group_path)
        name = name or source_details['name']
        path = path or source_details['path']

    export_file = os.path.join('exports/group', f'group-{group_path}-export.tgz')
    
    if not parent_id:
        logging.info(f'Importing top level group from {export_file} as {name} ({path})')
        with open(export_file, 'rb') as f:
            dest_gl.groups.import_group(f, name=name, path=path)
        logging.info(f'Top level group imported successfully from {export_file}')
    else:
        logging.info(f'Importing subgroup from {export_file} as {name} ({path})')
        with open(export_file, 'rb') as f:
            dest_gl.groups.import_group(f, parent_id=parent_id, name=name, path=path)
        logging.info(f'Subgroup imported successfully from {export_file}')

def get_all_projects(gl: gitlab.Gitlab, group_id: int, source_group_path: str) -> List[Dict[str, str]]:
    logging.info(f'Fetching all projects for group {group_id}')
    group = gl.groups.get(group_id)
    projects = []
    page = 1
    per_page = 100
    while True:
        group_projects = group.projects.list(include_subgroups=True, page=page, per_page=per_page)
        if not group_projects:
            break
        for project in group_projects:
            project_details = gl.projects.get(project.id)  # Fetch full project details
            default_branch = None
            try:
                # Attempt to fetch default_branch explicitly
                default_branch = project_details.default_branch
            except AttributeError:
                logging.warning(f"Default branch not found for project {project_details.name}.")
            
            full_path = project_details.namespace['full_path']
            relative_path = full_path.replace(source_group_path, '', 1).lstrip('/')
            projects.append({
                'project': project_details,
                'relative_path': relative_path,
                'name': project_details.name,
                'id': project_details.id,
                'path': project_details.path,
                'url': project_details.http_url_to_repo,
                'default_branch': default_branch or "main"  # Use fallback branch if missing
            })
        page += 1
    logging.info(f'Found {len(projects)} total projects in group {group_id}')
    return projects


def get_group_id_by_path(gl: gitlab.Gitlab, group_path: str) -> int:
    logging.info(f'Fetching group ID for path {group_path}')
    try:
        group = gl.groups.get(group_path)
        logging.info(f'Found group ID {group.id} for path: {group_path}')
        return group.id
    except gitlab.exceptions.GitlabGetError as e:
        logging.error(f'Group with path: {group_path} does not exist on {gl.url}: {e}')
        raise e