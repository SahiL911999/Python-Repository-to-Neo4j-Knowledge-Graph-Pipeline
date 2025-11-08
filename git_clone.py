import git
import os
import uuid
from pathlib import Path

def clone_repo(repo_url=None,branch_name=None, clone_dir=None):
    try:
        # Generate a unique directory name if no directory is provided
        if not clone_dir:
            clone_dir = str(uuid.uuid1())
        if branch_name is None:
            branch_name='main'
        
        # Create the full path where the repo will be cloned
        clone_path = Path(os.getcwd()) / clone_dir

        # Clone the repository into the specified directory
        print(f"Cloning repository from {repo_url} to {clone_path}")
        git.Repo.clone_from(repo_url, clone_path,branch=branch_name)
        print("Repository cloned successfully.")
        
        # Return the path as a Path object
        return clone_path

    except Exception as e:
        print(f"An error occurred while cloning the repository: {e}")


