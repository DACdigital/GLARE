import os
import time
import logging
import gitlab
from typing import List, Dict, Any
from retry import retry

@retry(tries=3, delay=10)
def download_project(export: Any, project_id: int):
    logging.info(f'Waiting for export to finish for project {project_id}')
    export.refresh()
    while export.export_status != 'finished':
        time.sleep(1)
        export.refresh()

    export_path = 'exports/projects'
    os.makedirs(export_path, exist_ok=True)

    with open(os.path.join(export_path, f'{project_id}-export.tgz'), 'wb') as f:
        export.download(streamed=True, action=f.write)
    logging.info(f'Export for project {project_id} downloaded successfully')

def export_projects(gl: gitlab.Gitlab, projects: List[Dict[str, str]]):
    """
    Export all projects to local files.
    """
    exports = []
    logging.info(f'Starting export for {len(projects)} projects')

    for project_info in projects:
        project = project_info['project']
        logging.info(f'Creating export for project {project.id}')
        export = project.exports.create()
        exports.append((project.id, export))

    for project_id, export in exports:
        download_project(export, project_id)

@retry(tries=3, delay=10)
def upload_project(gl: gitlab.Gitlab, project_id: int, project_path: str, 
                   project_name: str, namespace: str):
    """
    Upload a project to GitLab.
    """

    export_file = os.path.join('exports/projects', f'{project_id}-export.tgz')
    logging.info(f'Uploading project from {export_file} to path "{project_path}", '
                 f'namespace "{namespace}"')

    try:
        with open(export_file, 'rb') as f:
            output = gl.projects.import_project(f, path=project_path, name=project_name, 
                                                namespace=namespace)

        project_import = gl.projects.get(output['id'], lazy=True).imports.get()
        while project_import.import_status != 'finished':
            time.sleep(1)
            project_import.refresh()

        logging.info(f'Project {project_name} imported successfully')
        os.remove(export_file)
        logging.info(f'Deleted exported file: {export_file}')
    except Exception as e:
        logging.error(f"Failed to upload project {project_name}: {e}")


def import_projects(gl: gitlab.Gitlab, projects: List[Dict[str, str]], 
                   destination_parent_path: str, new_group_path: str):
    """
    Import projects to destination GitLab instance.
    """
    for project_info in projects:
        project_id = project_info['id']
        project_name = project_info['name']
        project_path = project_info['path']
        relative_path = project_info['relative_path']
        destination_namespace = os.path.join(destination_parent_path, new_group_path, 
                                           relative_path).rstrip('/')
        upload_project(gl, project_id, project_path, project_name, destination_namespace)