import os
import typer
import gitlab
from dotenv import load_dotenv
import logging

from migration.repository_manager import repositories_replacement
from migration.group_manager import export_group, import_group, get_all_projects, get_group_id_by_path
from migration.projects_manager import export_projects, import_projects
from migration.secrets_manager import migrate_group_variables, migrate_project_variables

app = typer.Typer()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_gitlab_clients():
    """Initialize GitLab clients from environment variables"""
    load_dotenv(override=True)
    
    gl_source = gitlab.Gitlab(
        url=os.getenv("GITLAB_SOURCE_URL"),
        private_token=os.getenv("GITLAB_SOURCE_TOKEN")
    )
    gl_destination = gitlab.Gitlab(
        url=os.getenv("GITLAB_TARGET_URL"),
        private_token=os.getenv("GITLAB_TARGET_TOKEN")
    )
    return gl_source, gl_destination

@app.command()
def migrate_group(
    source_path: str = typer.Option(..., help="Source group path (e.g. 'group/subgroup')"),
    dest_path: str = typer.Option(None, help="Destination parent group path"),
    new_name: str = typer.Option(None, help="New group name (optional)"),
    new_path: str = typer.Option(None, help="New group path (optional)"),
    top_level_group: bool = typer.Option(False, help="Create top level group")
):
    """Export group from source and import to destination"""
    gl_source, gl_destination = get_gitlab_clients()
    
    source_id = get_group_id_by_path(gl_source, source_path)
    export_group(gl_source, source_id)
    if top_level_group:
        import_group(gl_destination, gl_source, source_id, None, new_name, dest_path)
    else:
        dest_id = get_group_id_by_path(gl_destination, dest_path)
        import_group(gl_destination, gl_source, source_id, dest_id, new_name, new_path)
    typer.echo("Group migration completed successfully")

@app.command()
def migrate_projects(
    source_path: str = typer.Option(..., help="Source group path"),
    dest_path: str = typer.Option(..., help="Destination group path"),
    new_path: str = typer.Option(None, help="New group path (optional, defaults to source group path)"),
    top_level_group: bool = typer.Option(False, help="Create top level group")
):
    """Export projects from source and import to destination"""
    gl_source, gl_destination = get_gitlab_clients()
    
    source_id = get_group_id_by_path(gl_source, source_path)
    projects = get_all_projects(gl_source, source_id, source_path)
    
    export_projects(gl_source, projects)
    if top_level_group:
        new_path = ""
        logging.info(f"Exporting to top level group: {dest_path}")
        import_projects(gl_destination, projects, dest_path, new_path)
    elif not new_path:
        new_path = source_path.split('/')[-1]
        logging.info(f"Using source group path as new path: {new_path}")
        import_projects(gl_destination, projects, dest_path, new_path)
    else: 
        logging.info(f"Using new path as new path: {new_path}")
        import_projects(gl_destination, projects, dest_path, new_path)
    
    typer.echo("Projects migration completed successfully")

@app.command()
def migrate_secrets(
    source_path: str = typer.Option(..., help="Source group path"),
    dest_path: str = typer.Option(..., help="Destination group path"),
    new_path: str = typer.Option(None, help="New group path (optional, defaults to source group path)"),
    top_level_group: bool = typer.Option(False, help="Create top level group")
):
    """Migrate group and project variables"""
    gl_source, gl_destination = get_gitlab_clients()

    if top_level_group:
        dest_group_path = f"{dest_path}"
    elif not new_path:
        new_path = source_path.split('/')[-1]
        logging.info(f"Using source group path as new path: {new_path}")
        dest_group_path = f"{dest_path}/{new_path}"
    else:
        dest_group_path = f"{dest_path}/{new_path}"

    migrate_group_variables(gl_source, gl_destination, source_path, dest_group_path)
    migrate_project_variables(gl_source, gl_destination, source_path, dest_group_path)
    
    typer.echo("Secrets migration completed successfully")

@app.command()
def replace_repositories(
    source_path: str = typer.Option(..., help="Source group path (e.g. 'group/subgroup')"),
    dest_path: str = typer.Option(..., help="Destination group path, NOT the parent path"),
    new_path: str = typer.Option(None, help="New group path (optional, defaults to source group path)"),
    top_level_group: bool = typer.Option(False, help="Create top level group")
):
    """Replace repository URLs in all projects"""
    _, gl_destination = get_gitlab_clients()

    if top_level_group:
        logging.info(f"Exporting to top level group: {dest_path}")
        dest_group_path = f"{dest_path}"
    elif not new_path:
        new_path = source_path.split('/')[-1]
        logging.info(f"Using source group path as new path: {new_path}")
        dest_group_path = f"{dest_path}/{new_path}"
    else: 
        dest_group_path = f"{dest_path}/{new_path}"
    
    group_id = get_group_id_by_path(gl_destination, dest_group_path)
    projects = get_all_projects(gl_destination, group_id, dest_group_path)
    
    repositories_replacement(projects, gl_destination)
    
    typer.echo("Repository replacement completed successfully")

@app.command()
def migrate_all(
    source_path: str = typer.Option(..., help="Source group path (e.g. 'group/subgroup')"),
    dest_path: str = typer.Option(..., help="Destination parent group path"),
    new_name: str = typer.Option(None, help="New group name (optional, defaults to source group name)"),
    new_path: str = typer.Option(None, help="New group path (optional, defaults to source group path)"),
    top_level_group: bool = typer.Option(False, help="Create top level group")
):
    """Execute complete migration workflow"""
    try:
        # Step 1: Migrate group
        typer.echo("Starting group migration...")
        migrate_group(source_path, dest_path, new_name, new_path, top_level_group)

        # If new_path not provided, use last part of source_path
        if not new_path:
            new_path = source_path.split('/')[-1]
            logging.info(f"Using source group path as new path: {new_path}")

        # Step 2: Migrate projects
        typer.echo("Starting projects migration...")
        migrate_projects(source_path, dest_path, new_path, top_level_group)

        # Step 3: Migrate secrets
        typer.echo("Starting secrets migration...")

        migrate_secrets(source_path, dest_path, new_path, top_level_group)

        # Step 4: Replace repositories
        typer.echo("Starting repository URL replacement...")
        replace_repositories(source_path, dest_path, new_path, top_level_group)

        typer.echo("Complete migration workflow finished successfully!")
        
    except Exception as e:
        typer.echo(f"Migration failed: {str(e)}", err=True)
        raise

if __name__ == "__main__":
    app()

