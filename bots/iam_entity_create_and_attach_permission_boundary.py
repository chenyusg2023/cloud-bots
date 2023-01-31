'''
## iam_entity_create_and_attach_permission_boundary
What it does: Creates/Updates policy based on provided input, and attaches it as permission boundary to an iam entity (Role/User)
Usage: iam_entity_create_and_attach_permission_boundary [policy_name=<policy_name>], General policy name: CIEMSuggestion-<IAM-ENTITY-NAME>
Limitations: In case the iam entity (Role/User) already has an attached permission boundary the bot will fail.
Examples:  
    iam_entity_create_and_attach_permission_boundary policy_name=CIEMSuggestion
    iam_entity_create_and_attach_permission_boundary
'''

import boto3
from botocore.exceptions import ClientError

CG_POLICY_NAME = "CIEMSuggestion"


# Poll the account and check if the provided policy exists.
def check_for_policy(iam_client, policy_arn):
    delete_version = None
    text_output = ''
    keep_looking = True
    try:
        list_policy_response = iam_client.list_policy_versions(PolicyArn=policy_arn)
        while keep_looking:
            policy_versions = list_policy_response['Versions']
            for version in policy_versions:
                is_default_policy = version['IsDefaultVersion']
                if not is_default_policy:
                    delete_version = version['VersionId']
                    keep_looking = False
                    break
            if list_policy_response['IsTruncated']:
                list_policy_response = iam_client.list_policy_versions(PolicyArn=policy_arn,
                                                                       Marker=list_policy_response['Marker'])
            else:
                keep_looking = False
                if not delete_version:
                    text_output = 'Non default policy version to delete was not found.\n'
    except ClientError as e:
        error = e.response['Error']['Code']
        if error != 'NoSuchEntity':
            text_output = 'Unexpected error: %s \n' % e

    return text_output, delete_version


def create_policy(iam_client, policy_name, policy_doc):
    try:
        create_policy_response = iam_client.create_policy(
            PolicyName=policy_name,
            PolicyDocument=policy_doc,
            Description='Policy used for permissions boundary generated by CloudGuard CIEM',
            Tags=[
                {
                    'Key': 'Owner',
                    'Value': 'CloudGuard'
                },
            ]
        )
        text_output = 'Policy for permission boundary was created. Policy Name: %s\n' % policy_name

    except ClientError as e:
        text_output = 'Unexpected error: %s \n' % e

    return text_output


def create_policy_version(iam_client, policy_arn, policy_doc):
    try:
        create_policy_response = iam_client.create_policy_version(
            PolicyArn=policy_arn,
            PolicyDocument=policy_doc,
            SetAsDefault=True
        )
        text_output = 'New policy version - %s for permission boundary was created and set as default. Policy Name:  %s\n' \
                      % (create_policy_response['PolicyVersion']['VersionId'], policy_arn)

    except ClientError as e:
        text_output = 'Unexpected error: %s \n' % e

    return text_output


def delete_policy_version(iam_client, policy_arn, version_id):
    try:
        delete_policy_response = iam_client.delete_policy_version(
            PolicyArn=policy_arn,
            VersionId=version_id
        )
        text_output = 'Delete policy version - %s for permission boundary done. Policy Name: %s\n' % (
        version_id, policy_arn)
    except ClientError as e:
        text_output = 'Unexpected error: %s \n' % e

    return text_output


# Attach permission boundary to role
def attach_role_permission_boundary(iam_client, role_name, policy_arn):
    try:
        attach_policy_response = iam_client.put_role_permissions_boundary(
            RoleName=role_name,
            PermissionsBoundary=policy_arn
        )
        text_output = 'Permission boundary attached to role: %s\n' % role_name

    except ClientError as e:
        text_output = 'Failed to set permission boundary for role: %s error: %s\n' % (role_name, e)

    return text_output


# Attach permission boundary to user
def attach_user_permission_boundary(iam_client, user_name, policy_arn):
    try:
        attach_policy_response = iam_client.put_user_permissions_boundary(
            UserName=user_name,
            PermissionsBoundary=policy_arn
        )
        text_output = 'Permission boundary attached to user: \' %s \'\n' % user_name

    except ClientError as e:
        text_output = 'Failed to set permission boundary for user: %s error: %s \n' % (user_name, e)

    return text_output

def get_bot_spesific_configuration(params):
    policy_name_idx = None
    policy_doc = None
    dry_run = None
    for idx, param in enumerate(params):
        if 'policy_name=' in param:
            policy_name_idx = idx
        if 'SuggestedPolicy' in param:
            _, policy_doc = param.split('SuggestedPolicy:')
        if 'dryRun' in param:
            dry_run = True
    return policy_name_idx, policy_doc, dry_run

def set_policy_name(policy_name_idx, entity_name, cloud_account_id,params):
    # Get the policy_arn from the params
    if policy_name_idx is not None:
        _, name = params[policy_name_idx].split('=')
    else:
        name = CG_POLICY_NAME
    policy_name = '%s-%s' % (name, entity_name)
    policy_arn = "arn:aws:iam::%s:policy/%s" % (cloud_account_id, policy_name)

    return policy_name, policy_arn

def run_action(boto_session, rule, entity, params):
    text_output = ''
    cloud_account_id = entity['cloud_account_id']
    entity_type = entity['type']
    entity_name = entity['name']
    dry_run = False

    iam_client = boto_session.client('iam')

    policy_name_idx, policy_doc, dry_run = get_bot_spesific_configuration(params)
    policy_name, policy_arn = set_policy_name(policy_name_idx, entity_name, cloud_account_id, params)

    if dry_run:
        return f'The bot configuration is set to dry run once enabled the next actions will be conducted:\n' \
               f'1. Create a new policy version for policy arn: {policy_arn}\n' \
               f'2. Set the permission boundary of: {entity_name}, {entity_type} entity.\n'

    try:
        function_output, found_version = check_for_policy(iam_client, policy_arn)
        text_output = text_output + function_output

        if found_version:
            text_output = text_output + delete_policy_version(iam_client, policy_arn, found_version)
            text_output = text_output + create_policy_version(iam_client, policy_arn, policy_doc)
        elif 'Non default policy version to delete was not found' in text_output:
            text_output = text_output + create_policy_version(iam_client, policy_arn, policy_doc)
        else:
            text_output = text_output + create_policy(iam_client, policy_name, policy_doc)

        if 'User' in entity_type:
            text_output = text_output + attach_user_permission_boundary(iam_client, entity_name, policy_arn)
        else:
            text_output = text_output + attach_role_permission_boundary(iam_client, entity_name, policy_arn)

    except ClientError as e:
        text_output = 'Unexpected error: %s \n' % e

    return text_output
