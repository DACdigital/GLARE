import logging
import gitlab
import re
from typing import List, Any
import os 

def _get_variables(obj) -> List[Any]:
    """Get all variables from a GitLab object (group or project)"""
    try:
        return obj.variables.list(all=True)
    except gitlab.exceptions.GitlabGetError as e:
        logging.error(f"Failed to get variables: {e}")
        return []

def _create_variable(obj, var):
    """Create a variable in a GitLab object (group or project)"""
    try:
        source=os.getenv("GITLAB_SOURCE_URL").replace("https://", "")
        dest=os.getenv("GITLAB_TARGET_URL").replace("https://", "")
        var.value = re.sub(source, dest, var.value)
        
        obj.variables.create({
            'key': var.key,
            'value': var.value,
            'protected': var.protected,
            'masked': var.masked,
            'environment_scope': var.environment_scope
        })
        logging.info(f"Created variable {var.key}")
    except gitlab.exceptions.GitlabCreateError as e:
        logging.error(f"Failed to create variable {var.key}: {e}")

def _get_all_subgroups(gl: gitlab.Gitlab, group_path: str) -> List[str]:
    """Recursively get all subgroups paths"""
    try:
        group = gl.groups.get(group_path)
        subgroups = group.subgroups.list(all=True)
        
        all_groups = {group_path}
        
        for subgroup in subgroups:
            full_path = subgroup.full_path
            
            all_groups.add(full_path)
            
            all_groups.update(_get_all_subgroups(gl, full_path))
            
        return sorted(list(all_groups))
    except gitlab.exceptions.GitlabGetError as e:
        logging.error(f"Failed to get subgroups for {group_path}: {e}")
        return []

def migrate_group_variables(source_gl: gitlab.Gitlab, dest_gl: gitlab.Gitlab, 
                          source_group_path: str, dest_group_path: str):
    """Migrate variables from source group and all its subgroups"""
    try:

        source_groups = _get_all_subgroups(source_gl, source_group_path)
        top_parent_group = source_groups[0]

        for source_group_path in source_groups:

            relative_path = source_group_path.replace(top_parent_group, '', 1).lstrip('/')
            dest_group_full_path = f"{dest_group_path}/{relative_path}" if relative_path else dest_group_path
            
            try:
                source_group = source_gl.groups.get(source_group_path)
                dest_group = dest_gl.groups.get(dest_group_full_path)
                
                logging.info(f"Migrating variables from group {source_group_path} to {dest_group_full_path}")
                group_vars = _get_variables(source_group)
                
                for var in group_vars:
                    _create_variable(dest_group, var)
                    
            except gitlab.exceptions.GitlabGetError as e:
                logging.error(f"Failed to access group {source_group_path} or {dest_group_full_path}: {e}")
                continue
                
    except gitlab.exceptions.GitlabGetError as e:
        logging.error(f"Failed to access group: {e}")

def migrate_project_variables(source_gl: gitlab.Gitlab, dest_gl: gitlab.Gitlab,
                            source_group_path: str, dest_group_path: str):
    """Migrate variables from all projects in source group to destination group"""
    try:
        source_group = source_gl.groups.get(source_group_path)
        source_projects = source_group.projects.list(all=True, include_subgroups=True)
        
        for source_project in source_projects:
            source_project = source_gl.projects.get(source_project.id)
            
            try:
                relative_path = source_project.path_with_namespace.replace(source_group_path + '/', '')
                dest_project_path = f"{dest_group_path}/{relative_path}"
                dest_project = dest_gl.projects.get(dest_project_path)
                
                logging.info(f"Migrating variables from project {source_project.path_with_namespace}")
                project_vars = _get_variables(source_project)
                
                for var in project_vars:
                    _create_variable(dest_project, var)
                    
            except gitlab.exceptions.GitlabGetError as e:
                logging.error(f"Failed to find destination project {dest_project_path}: {e}")
                continue
                
    except gitlab.exceptions.GitlabGetError as e:
        logging.error(f"Failed to access group: {e}")