# GLARE - GitLab Automated Replication & Export

## Overview
This project provides a set of scripts to migrate GitLab groups, projects, repositories and secret variables.
It was orinaly used for migration from gitlab SAAS to onprem, but it'll work in case of migraiton from onprem to onprem as well. 

## Installation 
Required python version >=3.12.1

Use pip to install requirements.
```bash
pip install -r requirements.txt
```
## Environment Configuration

MOdify `.env` file in the project root with the following configuration:

```ini
# GitLab API Access
GITLAB_SOURCE_URL=https://gitlab.com # Source url of the Repository; typically it will be https://gitlab.com if you're moving from SaaS solution, but could be a different address if you're migrating between two on-premise hosted platforms
GITLAB_SOURCE_TOKEN=your_source_gitlab_token #Generated api token for source Gitlab. Use token with minimal scope "api"
GITLAB_TARGET_URL=https://gitlab.destination.com # Destination  url of the Repository
GITLAB_TARGET_TOKEN=your_target_gitlab_token #Generated api token for destination Gitlab. Use token with minimal scope "api"
REPLACEMENTS = {'gitlab.com':'your.gitlab.com', "foo":"bar"} #dict of strings in repository to be replaced (from foo in the orginal repository to bar in the migrated repository)
```

## Structure 
Project consists of 4 migration scripts:
- **`group_manager.py`**: Creates a new GitLab group and subgroups, utilizing import/export api
- **`project_manager.py`**: Migrates projects to group, utilizing import/export api
- **`repository_manager.py`**: Modification of the imported repository, it'll go through files in the repository, change the strings based on REPLACEMENTS dict and create a MR with the changes 
- **`secrets_manager.py`**: Migrates secret variables, both for group and projects in that group. 

## Execution
Use `migrate-all` for a complete migration or run individual commands as needed.
## Available Commands

### **Scripts Parameters:**
- `--source-path` *(required)* → Path of the source group (e.g., `group/subgroup`).
- `--dest-path` *(optional)* → Destination parent group path.
- `--new-name` *(optional)* → New name for the group.
- `--new-path` *(optional)* → New group path. Used in migrate-group and migrate-all
- `--top-level-group` *(optional, default: `False`)* → If set, creates the group as a top-level group.

### **1. Migrate Group**

#### **Usage:**
```bash
python glare.py migrate-group --source-path <source_path> --dest-path <dest_path> [--new-name <new_name>] [--new-path <new_path>] [--top-level-group]
```

#### **Description:**
Exports a GitLab group from the source instance and imports it into the destination instance.

#### **Execution Steps:**
1. Gets the group ID from the source GitLab instance.
2. Exports the group.
3. Imports the group as a top-level entity if `top_level_group` is set.
4. Otherwise, imports it under the destination group.

---

### **2. Migrate Projects**

#### **Usage:**
```bash
python glare.py migrate-projects --source-path <source_path> --dest-path <dest_path> [--new-path <new_path>] [--top-level-group]
```

#### **Description:**
Exports projects from the source group and imports them into the destination group.

#### **Execution Steps:**
1. Retrieves all projects under the source group.
2. Exports the projects.
3. Determines the destination group path:
   - Uses `new_path` if provided.
   - Defaults to the last part of `source_path`.
4. Imports projects into the destination.

---

### **3. Migrate Secrets**

#### **Usage:**
```bash
python glare.py migrate-secrets --source-path <source_path> --dest-path <dest_path> [--new-path <new_path>] [--top-level-group]
```

#### **Description:**
Migrates group and project secrets (CI/CD variables) from the source group to the destination group.

#### **Execution Steps:**
1. Migrates group variables.
2. Migrates project variables.

---

### **4. Replace Repositories**

#### **Usage:**
```bash
python glare.py replace-repositories --source-path <source_path> --dest-path <dest_path> [--new-path <new_path>] [--top-level-group]
```

#### **Description:**
Updates strings in repository in all migrated projects defined by REPLACEMENTS.

#### **Execution Steps:**
1. Determines the destination group path.
2. Fetches all projects under the destination group.
3. Replaces repository strings for all projects.

---

### **5. Migrate All**

#### **Usage:**
```bash
python glare.py migrate-all --source-path <source_path> --dest-path <dest_path> [--new-name <new_name>] [--new-path <new_path>] [--top-level-group]
```

#### **Description:**
Executes a full migration workflow, including:
- Group migration
- Project migration
- Secrets migration
- Repository string replacement


## Examples 
NOTE: When using --top-level-group there is no need to specify --new-path, param --dest-path will be used.
If no --top-level-group is specified the --dest-path must exists on the new instance. 

### Migrate all 
#### Case 1 - top-level-group
```bash
python glare.py migrate-all --source-path foo/bar --dest-path foobar --top-level-group
```
It will migrate the group abr including all subgroups, projects, variables from path gitlab.com/foo/bar to your.gitlab.com/foobar. It'll default to the orginal group name as no --new-name is specified. 

#### Case 2 subgroup 
```bash
python glare.py migrate-all --source-path foo/bar --dest-path foo
```
The script will assume the foo group exists on the new instance. It will migrate group bar including all subgroups, projects, variables from path gitlab.com/foo/bar to your.gitlab.com/foo/bar. It'll default to the orginal group name as no --new-name is specified. 

#### Case 3 subgroup, change name and  path  
```bash
python glare.py migrate-all --source-path foo/bar --dest-path foo  --new-path rab --new-name lorem
```
The script will assume the foo group exists on the new instance. It will migrate group bar including all subgroups, projects, variables from path gitlab.com/foo/bar to your.gitlab.com/foo/rab naming the group lorem. 

### Migrate secrets/projects/replace-repos 
Logic applies to migrate-secrets, migrate-projects, replace-repositories
#### Case 1 
```bash
python glare.py migrate-secrets --source-path foo/bar --dest-path foo
```
The command will migrate all secrets from group gitlab.com/foo/bar and projects in the group to group your.gitlab.com/foo/bar. It'll assume group bar exists. 

#### Case 2
```bash
python glare.py migrate-secrets --source-path foo/bar --dest-path foo --new-path lorem
```
The command will migrate all secrets from group gitlab.com/foo/bar and projects in the group to group your.gitlab.com/foo/lorem. It'll assume group lorem exists.

#### Case 3
```bash
python glare.py migrate-secrets --source-path foo/bar --dest-path lorem --top-level-group
```
The command will migrate all secrets from group gitlab.com/foo/bar and projects in the group to group your.gitlab.com/lorem. It'll assume group lorem exists.

### Migrate group 
#### Case 1
```bash
python glare.py migrate-group --source-path foo/bar --dest-path lorem --top-level-group
```
The command will migrate group and subgroups gitlab.com/foo/bar to top-level group your.gitlab.com/lorem.

#### Case 2
```bash
python glare.py migrate-group --source-path foo/bar --dest-path lorem 
```
The command will migrate group and subgroups gitlab.com/foo/bar to sub-level group your.gitlab.com/lorem/bar.