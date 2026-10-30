import os
import re
import subprocess
from datetime import datetime

GLOBAL_ASSEMBLY_INFO_FILE_PATH = 'src/GlobalAssemblyInfo.cs'

def get_remote_url() -> str:
    repository = os.getenv("CI_REPOSITORY_URL", "")
    user = f"git:{os.getenv('RELEASE_PAT')}"
    (_, url) = repository.split("@")
    return f"https://{user}@{url.replace(':', '/')}"

def configure_git(git_email, git_username) -> None:
    os.system(f"git config user.email \"{git_email}\"")
    os.system(f"git config user.name \"{git_username}\"")
    os.system(f"git remote set-url origin {get_remote_url()}")

def checkout_default_branch() -> None:
    branch = os.getenv("CI_DEFAULT_BRANCH")
    os.system(f"git fetch origin {branch}:{branch}")
    os.system(f"git checkout {branch}")

def checkout_branch(name) -> None:
    os.system(f"git checkout -b {name}")

def push_branch(name) -> None:
    os.system(f"git push --set-upstream origin {name}")

def create_commit(message) -> None:
    os.system(f"git commit -m \"{message}\"")

def create_branch(version, branch_name, commit_message) -> None:
    checkout_default_branch()
    checkout_branch(branch_name)
    update_app_version(version)
    create_commit(commit_message)
    push_branch(branch_name)

def create_debug_branch(version, commit_message) -> None:
    create_branch(version, f"debug/{version}", commit_message)

def create_release_branch(version, commit_message) -> None:
    create_branch(version, f"release/{version}", commit_message)

def delete_previous_test_release_branches() -> None:
    ls_remote = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", "release/9.9.9-from-*"],
        capture_output=True,
        text=True,
        check=False,
    )

    if ls_remote.returncode != 0:
        stdout = ls_remote.stdout.strip() if ls_remote.stdout else "<empty>"
        stderr = ls_remote.stderr.strip() if ls_remote.stderr else "<empty>"
        print(
            "Failed to list previous 9.9.9 release branches. "
            f"exit_code={ls_remote.returncode}, stdout={stdout}, stderr={stderr}"
        )
        return

    branches = []
    for line in ls_remote.stdout.splitlines():
        ref = line.split("\t")[-1].strip()
        if ref.startswith("refs/heads/"):
            branches.append(ref.replace("refs/heads/", "", 1))

    if len(branches) == 0:
        print("No previous release/9.9.9-from-* branches found.")
        return

    for branch in branches:
        print(f"Deleting previous branch {branch}")
        delete_result = subprocess.run(
            ["git", "push", "origin", "--delete", branch],
            capture_output=True,
            text=True,
            check=False,
        )
        if delete_result.returncode != 0:
            stdout = delete_result.stdout.strip() if delete_result.stdout else "<empty>"
            stderr = delete_result.stderr.strip() if delete_result.stderr else "<empty>"
            print(
                f"Failed to delete branch {branch}. "
                f"exit_code={delete_result.returncode}, stdout={stdout}, stderr={stderr}"
            )

def update_app_version(version) -> None:
    content = ''
    with open(GLOBAL_ASSEMBLY_INFO_FILE_PATH, encoding='utf-8') as f:
        content = f.read()
        content = re.sub(r"(AssemblyVersion\(\")([0-9]+\.[0-9]+\.[0-9]+)", rf"\g<1>{version}", content)
        content = re.sub(r"(AssemblyFileVersion\(\")([0-9]+\.[0-9]+\.[0-9]+)", rf"\g<1>{version}", content)
    with open(GLOBAL_ASSEMBLY_INFO_FILE_PATH, 'w') as f:
        f.write(content)

    os.system(f"git add {GLOBAL_ASSEMBLY_INFO_FILE_PATH}")

version = os.getenv('APP_VERSION')
if version == None:
    raise Exception("Missing env variable APP_VERSION")

configure_git(os.getenv('RELEASE_GIT_EMAIL'), os.getenv('RELEASE_GIT_USERNAME'))

delete_previous_test_release_branches()

create_release_branch(version, f"Increase app version to {version}")
create_debug_branch(version, f"Increase app version to {version}")

dateTime = datetime.now().strftime("%Y%m%d%H%M%S")
create_branch('9.9.9', f"release/9.9.9-from-{version}-{dateTime}", f"Build app version 9.9.9 to test {version} installer")