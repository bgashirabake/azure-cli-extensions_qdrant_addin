#!/usr/bin/env python

# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

from subprocess import check_output
from util import SRC_PATH
import json
import logging
import os
import shlex
import subprocess
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
logger.addHandler(ch)


def get_all_tests():
    all_tests = []
    for src_d in os.listdir(SRC_PATH):
        src_d_full = os.path.join(SRC_PATH, src_d)
        if not os.path.isdir(src_d_full):
            continue
        pkg_name = next((d for d in os.listdir(src_d_full) if d.startswith('azext_')), None)

        # If running in Travis CI, only run tests for edited extensions
        commit_range = os.environ.get('TRAVIS_COMMIT_RANGE')
        if commit_range and not check_output(
                ['git', '--no-pager', 'diff', '--name-only', commit_range, '--', src_d_full]):
            continue

        # Running in Azure DevOps
        cmd_tpl = 'git --no-pager diff --name-only origin/{commit_start} {commit_end} -- {code_dir}'
        ado_branch_last_commit = os.environ.get('ADO_PULL_REQUEST_LATEST_COMMIT')
        ado_target_branch = os.environ.get('ADO_PULL_REQUEST_TARGET_BRANCH')
        if ado_branch_last_commit and ado_target_branch:
            if ado_branch_last_commit == '$(System.PullRequest.SourceCommitId)':
                # default value if ADO_PULL_REQUEST_LATEST_COMMIT not set in ADO
                continue
            elif ado_target_branch == '$(System.PullRequest.TargetBranch)':
                # default value if ADO_PULL_REQUEST_TARGET_BRANCH not set in ADO
                continue
            else:
                cmd = cmd_tpl.format(commit_start=ado_target_branch, commit_end=ado_branch_last_commit,
                                     code_dir=src_d_full)
                if not check_output(shlex.split(cmd)):
                    continue

        # Find the package and check it has tests
        test_dir = os.path.isdir(os.path.join(src_d_full, pkg_name, 'tests'))
        if pkg_name and test_dir:
            # [('azext_healthcareapis', '/mnt/vss/_work/1/s/src/healthcareapis')]
            all_tests.append((pkg_name, src_d_full))
            # azext_healthcareapis
            extension_name = all_tests[0][0]
            # healthcareapis
            _, original_extension_name = extension_name.split('_', 1)
        else:
            logger.error(f'can not any test in {test_dir}')
            with open('python_version.txt', 'w') as f:
                f.write('false')
            sys.exit(0)

    logger.info(f'ado_branch_last_commit: {ado_branch_last_commit}, '
                f'ado_target_branch: {ado_target_branch}, '
                f'detect which extension need to test: {all_tests}.')
    return original_extension_name, extension_name


def get_min_version(original_extension_name, extension_name):
    try:
        with open(os.path.join(SRC_PATH, original_extension_name, extension_name, 'azext_metadata.json'), 'r') as f:
            min_version = json.load(f)['azext.minCliCoreVersion']
            logger.info(f'find minCliCoreVersion: {min_version}')
            return min_version
    except Exception as e:
        logger.error(f'can not get minCliCoreVersion: {e}')
        with open('python_version.txt', 'w') as f:
            f.write('false')
        sys.exit(0)


def get_python_version(min_version):
    logger.info(f'checkout to minCliCoreVersion: {min_version}')
    az_min_version = 'azure-cli-' + min_version
    azure_cli_path = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(SRC_PATH))), 'azure-cli')
    # checkout to min cli version
    cmd = ['git', 'checkout', az_min_version]
    run_command(cmd, check_return_code=True, cwd=azure_cli_path)
    # display cli version
    cmd = ['az', '--version']
    run_command(cmd, check_return_code=True)
    try:
        core_path = os.path.join(azure_cli_path, 'src', 'azure-cli-core')
        with open(os.path.join(core_path, 'setup.py'), 'r') as f:
            for line in f.readlines():
                if 'Programming Language :: Python :: ' in line:
                    _, _, python_version = line.split(' :: ')
                    python_version = python_version.split('\'')[0]
        logger.info(f'return python verison: {python_version}')
        with open('python_version.txt', 'w') as f:
            f.write(python_version)
    except Exception as e:
        logger.error(f'can not get python_version: {e}')
        with open('python_version.txt', 'w') as f:
            f.write('false')
        sys.exit(0)


def run_command(cmd, check_return_code=False, cwd=None):
    error_flag = False
    logger.info(f'cmd: {cmd}')
    try:
        out = subprocess.run(cmd, check=True, cwd=cwd)
        if check_return_code and out.returncode:
            raise RuntimeError(f"{cmd} failed")
    except subprocess.CalledProcessError:
        error_flag = True
    return error_flag


def main():
    original_extension_name, extension_name = get_all_tests()
    min_version = get_min_version(original_extension_name, extension_name)
    get_python_version(min_version)


if __name__ == '__main__':
    main()
