import os
import subprocess
import gitlab
import tempfile
import logging
import json 
from pathlib import Path
import ast


def clone_repository(project, gl: gitlab.Gitlab) -> str:
    base_path = Path(os.getcwd())
    repositories_path = base_path / 'repositories'
    project_path = repositories_path / project['path']
    
    os.makedirs(repositories_path, exist_ok=True)
    
    if os.path.exists(project_path):
        logging.warning(f"Directory {project_path} already exists, removing it")
        subprocess.run(['rm', '-rf', str(project_path)], check=True)
    
    repo_url = project['url'].replace('https://', f'https://oauth2:{gl.private_token}@')
    
    logging.info(f"Cloning repository {project['path']} to {project_path}")
    
    try:
        subprocess.run(
            ['git', 'clone', repo_url, str(project_path)],
            check=True,
            capture_output=True,
            text=True
        )
        logging.info(f"Successfully cloned {project['path']} to {project_path}")
        return str(project_path)
        
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to clone {project['path']}: {e.stderr}")
        raise

def search_and_replace(directory: str) -> None:
    file_patterns = {
        '.yaml',    
        '.yml',     
        '.toml',    
        '.ini',     
        '.sh',      
        'Dockerfile',  
        '.gitlab-ci.yml',
        'build.gradle',
        'pom.xml'
    }

    replacements = ast.literal_eval(os.environ["REPLACEMENTS"])

    skip_dirs = {'.git'}

    logging.info(f"Starting search and replace in {directory}")
    
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        for file in files:
            if any(file.lower().endswith(pat.lower()) for pat in file_patterns):
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    new_content = content
                    for old, new in replacements.items():
                        if old in new_content:
                            new_content = new_content.replace(old, new)
                            logging.info(f"Replaced '{old}' with '{new}' in {file_path}")
                    
                    if new_content != content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                            
                except UnicodeDecodeError:
                    logging.debug(f"Skipping binary file: {file_path}")
                except Exception as e:
                    logging.error(f"Error processing {file_path}: {str(e)}")
                    continue

    logging.info("Completed search and replace operation")

def create_branch_and_commit(directory: str, branch_name: str) -> bool:
    """
    Create a new branch and commit changes if there are any.
    
    Args:
        directory: Repository directory path
        branch_name: Name of the new branch
    
    Returns:
        bool: True if changes were committed, False if no changes
    """
    try:
        # Create and checkout new branch
        subprocess.run(['git', 'checkout', '-b', branch_name], cwd=directory, check=True)
        
        # Check if there are any changes to commit
        status = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=directory,
            check=True,
            capture_output=True,
            text=True
        )
        
        if not status.stdout.strip():
            logging.info("No changes to commit")
            return False
            
        # Add and commit changes
        subprocess.run(['git', 'add', '.'], cwd=directory, check=True)
        subprocess.run(
            ['git', 'commit', '--no-gpg-sign', '-m', 'Replace references in repository code (gitlab migration)'],
            cwd=directory,
            check=True
        )
        logging.info(f"Created branch '{branch_name}' and committed changes")
        return True
        
    except subprocess.CalledProcessError as e:
        logging.error(f"Git operation failed: {e.stderr if hasattr(e, 'stderr') else str(e)}")
        raise

def push_branch(directory, branch_name):
    subprocess.run(['git', 'push', '--set-upstream', 'origin', branch_name], cwd=directory, check=True)

def create_merge_request(gl, project, source_branch, target_branch ,title, description):
    mr = project.mergerequests.create({
        'source_branch': source_branch,
        'target_branch': target_branch,
        'title': title,
        'description': description,
        'labels': ['gitlab-migration']
    })
    logging.info(f'Merge request created: {mr.web_url}')

def replace_repository_code(gl, project):
    project_path = clone_repository(project, gl)
    search_and_replace(project_path)
    
    if create_branch_and_commit(project_path, 'replace-gitlab-url'):
        push_branch(project_path, 'replace-gitlab-url')
        create_merge_request(
            gl, 
            project['project'], 
            'replace-gitlab-url',
            project['default_branch'], 
            'Replace strings occurrences', 
            'This MR replaces all strings defined in REPLACEMENTS variable used in migration script'
        )
    else:
        logging.info(f"No changes needed for {project['path']}")

def repositories_replacement(projects, gl):
    """Replace strings in all repositories

    Args:
        projects (_type_): _description_
        gl (_type_): _description_
    """
    for project in projects:
        try:
            replace_repository_code(gl, project)
        except Exception as e:
            logging.error(f"Error processing repository {project['path']}: {e}")
            continue

    logging.info('Replacements completed')