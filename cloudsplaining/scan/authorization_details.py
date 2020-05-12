"""Represents the entire JSON file generated by the aws iam get-account-authorization-details command."""
# Copyright (c) 2020, salesforce.com, inc.
# All rights reserved.
# Licensed under the BSD 3-Clause license.
# For full license text, see the LICENSE file in the repo root
# or https://opensource.org/licenses/BSD-3-Clause
import logging
from operator import itemgetter
from policy_sentry.querying.all import get_all_service_prefixes

# from cloudsplaining.shared.constants import DEFAULT_EXCLUSIONS_CONFIG
from cloudsplaining.scan.policy_detail import PolicyDetails
from cloudsplaining.scan.principal_detail import PrincipalTypeDetails
from cloudsplaining.output.findings import (
    Findings,
    UserFinding,
    GroupFinding,
    RoleFinding,
    PolicyFinding,
)

# from cloudsplaining.shared.exclusions import is_name_excluded
from cloudsplaining.shared.exclusions import Exclusions, DEFAULT_EXCLUSIONS

all_service_prefixes = get_all_service_prefixes()
logger = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes
class AuthorizationDetails:
    """
    Represents the entire JSON file generated by the aws iam get-account-authorization-details command.
    """

    def __init__(self, auth_json):
        self.auth_json = auth_json
        self.policies = PolicyDetails(auth_json.get("Policies", None))
        self.user_detail_list = PrincipalTypeDetails(
            auth_json.get("UserDetailList", None)
        )
        self.group_detail_list = PrincipalTypeDetails(
            auth_json.get("GroupDetailList", None)
        )
        self.role_detail_list = PrincipalTypeDetails(
            auth_json.get("RoleDetailList", None)
        )
        self.findings = Findings()
        self.customer_managed_policies_in_use = self._customer_managed_policies_in_use()
        self.aws_managed_policies_in_use = self._aws_managed_policies_in_use()

    def _aws_managed_policies_in_use(self):
        aws_managed_policies = []
        for policy in self.policies.policy_details:
            if "arn:aws:iam::aws:" in policy.arn:
                aws_managed_policies.append(policy.policy_name)
        # Policies attached to groups
        for principal in self.group_detail_list.principals:
            for attached_managed_policy in principal.attached_managed_policies:
                if "arn:aws:iam::aws:" in attached_managed_policy.get("PolicyArn"):
                    aws_managed_policies.append(
                        attached_managed_policy.get("PolicyName")
                    )
        # Policies attached to users
        for principal in self.user_detail_list.principals:
            for attached_managed_policy in principal.attached_managed_policies:
                if "arn:aws:iam::aws:" in attached_managed_policy.get("PolicyArn"):
                    aws_managed_policies.append(
                        attached_managed_policy.get("PolicyName")
                    )
        # Policies attached to roles
        for principal in self.role_detail_list.principals:
            for attached_managed_policy in principal.attached_managed_policies:
                if "arn:aws:iam::aws:" in attached_managed_policy.get("PolicyArn"):
                    aws_managed_policies.append(
                        attached_managed_policy.get("PolicyName")
                    )
        aws_managed_policies = list(dict.fromkeys(aws_managed_policies))
        return aws_managed_policies

    def _customer_managed_policies_in_use(self):
        customer_managed_policies = []
        for policy in self.policies.policy_details:
            if "arn:aws:iam::aws:" not in policy.arn:
                customer_managed_policies.append(policy.policy_name)
        # Policies attached to groups
        for principal in self.group_detail_list.principals:
            for attached_managed_policy in principal.attached_managed_policies:
                # Skipping coverage here because it would be redundant
                if "arn:aws:iam::aws:" not in attached_managed_policy.get(
                    "PolicyArn"
                ):  # pragma: no cover
                    customer_managed_policies.append(
                        attached_managed_policy.get("PolicyName")
                    )
        # Policies attached to users
        for principal in self.user_detail_list.principals:
            for attached_managed_policy in principal.attached_managed_policies:
                # Skipping coverage here because it would be redundant
                if "arn:aws:iam::aws:" not in attached_managed_policy.get(
                    "PolicyArn"
                ):  # pragma: no cover
                    customer_managed_policies.append(
                        attached_managed_policy.get("PolicyName")
                    )
        # Policies attached to roles
        for principal in self.role_detail_list.principals:
            for attached_managed_policy in principal.attached_managed_policies:
                # Skipping coverage here because it would be redundant
                if "arn:aws:iam::aws:" not in attached_managed_policy.get(
                    "PolicyArn"
                ):  # pragma: no cover
                    customer_managed_policies.append(
                        attached_managed_policy.get("PolicyName")
                    )
        customer_managed_policies = list(dict.fromkeys(customer_managed_policies))
        return customer_managed_policies

    @property
    def groups(self):
        """A list of the group names in the account, according to the account authorization details."""
        group_names = []
        for principal in self.group_detail_list.principals:
            group_names.append(principal.name)
        return group_names

    @property
    def roles(self):
        """A list of the role names in the account, according to the account authorization details."""
        role_names = []
        for principal in self.role_detail_list.principals:
            role_names.append(principal.name)
        return role_names

    @property
    def users(self):
        """A list of the user names in the account, according to the account authorization details."""
        user_names = []
        for principal in self.user_detail_list.principals:
            user_names.append(principal.name)
        return user_names

    @property
    def principals(self):
        """Get a list of PrincipalDetail objects for all principals - Users, Groups, or Roles - in the account."""
        all_principals = []
        # Users
        for principal in self.user_detail_list.principals:
            all_principals.append(principal)
        # Groups
        for principal in self.group_detail_list.principals:
            all_principals.append(principal)
        # Roles
        for principal in self.role_detail_list.principals:
            all_principals.append(principal)
        return all_principals

    @property
    def principal_policy_mapping(self):
        """
        Returns a mapping of principals vs the policies that they are attached to - either inline or managed.
        """
        principal_policy_mapping = []

        for principal in self.principals:
            # Inline Policies
            if principal.inline_principal_policies:
                for inline_policy in principal.inline_principal_policies:
                    entry = dict(
                        Principal=principal.name,
                        Type=principal.principal_type,
                        PolicyType="Inline",
                        ManagedBy="Customer",
                        PolicyName=inline_policy.get("PolicyName"),
                        GroupMembership=None,
                    )
                    principal_policy_mapping.append(entry)
            # AttachedManagedPolicies
            if principal.attached_managed_policies:
                for attached_managed_policy in principal.attached_managed_policies:
                    if "arn:aws:iam::aws:" in attached_managed_policy.get("PolicyArn"):
                        managed_by = "AWS"
                    else:
                        managed_by = "Customer"
                    entry = dict(
                        Principal=principal.name,
                        Type=principal.principal_type,
                        PolicyType="Managed",
                        ManagedBy=managed_by,
                        PolicyName=attached_managed_policy.get("PolicyName"),
                        GroupMembership=None,
                    )
                    principal_policy_mapping.append(entry)

            # While users might have inline policies or managed policies,
            # their findings will need to reflect their group membership findings as well.
            # So we need to run that loop again, finding the data for their groups and adding it.
            if principal.principal_type == "User":
                group_memberships = principal.group_member
                for group_membership in group_memberships:
                    for some_principal in self.principals:
                        if (
                            some_principal.principal_type == "Group"
                            and some_principal.name == group_membership
                        ):
                            if some_principal.inline_principal_policies:
                                for (
                                    inline_policy
                                ) in some_principal.inline_principal_policies:
                                    entry = dict(
                                        Principal=principal.name,
                                        Type=principal.principal_type,
                                        PolicyType="Inline",
                                        ManagedBy="Customer",
                                        PolicyName=inline_policy.get("PolicyName"),
                                        GroupMembership=principal.group_member,
                                    )
                                    principal_policy_mapping.append(entry)
                            # AttachedManagedPolicies
                            if some_principal.attached_managed_policies:
                                for (
                                    attached_managed_policy
                                ) in some_principal.attached_managed_policies:
                                    if (
                                        "arn:aws:iam::aws:"
                                        in attached_managed_policy.get("PolicyArn")
                                    ):
                                        managed_by = "AWS"
                                    else:
                                        managed_by = "Customer"
                                    entry = dict(
                                        Principal=principal.name,
                                        Type=principal.principal_type,
                                        PolicyType="Managed",
                                        ManagedBy=managed_by,
                                        PolicyName=attached_managed_policy.get(
                                            "PolicyName"
                                        ),
                                        GroupMembership=principal.group_member,
                                    )
                                    principal_policy_mapping.append(entry)
        # Sort it
        principal_policy_mapping = sorted(
            principal_policy_mapping,
            key=itemgetter("Type", "Principal", "PolicyType", "PolicyName"),
        )
        return principal_policy_mapping

    def missing_resource_constraints(
        self, exclusions=DEFAULT_EXCLUSIONS, modify_only=True
    ):
        """Scan the account authorization details for missing resource constraints."""
        if not isinstance(exclusions, Exclusions):
            raise Exception(
                "The provided exclusions is not the Exclusions object type. "
                "Please use the Exclusions object."
            )
        self.findings = Findings(exclusions)
        print("-----USERS-----")
        self.scan_principal_type_details(self.user_detail_list, exclusions, modify_only)
        print("-----GROUPS-----")
        self.scan_principal_type_details(
            self.group_detail_list, exclusions, modify_only
        )
        print("-----ROLES-----")
        self.scan_principal_type_details(self.role_detail_list, exclusions, modify_only)
        print("-----POLICIES-----")
        self.findings.principal_policy_mapping = self.principal_policy_mapping
        self.scan_policy_details(exclusions, modify_only)
        return self.findings.json

    def scan_policy_details(self, exclusions=DEFAULT_EXCLUSIONS, modify_only=True):
        """Scan the PolicyDetails block of the account authorization details output."""
        if not isinstance(exclusions, Exclusions):
            raise Exception(
                "The provided exclusions is not the Exclusions object type. "
                "Please use the Exclusions object."
            )
        for policy in self.policies.policy_details:
            print(f"Scanning policy: {policy.policy_name}")
            actions_missing_resource_constraints = []
            if exclusions.is_policy_excluded(
                policy.policy_name
            ) or exclusions.is_policy_excluded(policy.full_policy_path):
                print(f"\tExcluded policy name: {policy.policy_name}")
            else:
                for statement in policy.policy_document.statements:
                    if modify_only:
                        if statement.effect == "Allow":
                            actions_missing_resource_constraints.extend(
                                statement.missing_resource_constraints_for_modify_actions(
                                    exclusions
                                )
                            )
                    else:
                        if statement.effect == "Allow":
                            actions_missing_resource_constraints.extend(
                                statement.missing_resource_constraints(exclusions)
                            )
                if actions_missing_resource_constraints:
                    actions_missing_resource_constraints = list(
                        dict.fromkeys(actions_missing_resource_constraints)
                    )  # remove duplicates
                    actions_missing_resource_constraints.sort()
                    policy_finding = PolicyFinding(
                        policy_name=policy.policy_name,
                        arn=policy.arn,
                        actions=actions_missing_resource_constraints,
                        policy_document=policy.policy_document,
                        exclusions=exclusions,
                    )
                    self.findings.add_policy_finding(policy_finding)

    def scan_principal_type_details(
        self,
        principal_type_detail_list,
        exclusions=DEFAULT_EXCLUSIONS,
        modify_only=True,
    ):
        """Scan the UserDetailList, GroupDetailList, or RoleDetailList
        blocks of the account authorization details output."""
        if not isinstance(exclusions, Exclusions):
            raise Exception(
                "The provided exclusions is not the Exclusions object type. "
                "Please use the Exclusions object."
            )
        # TODO: Fix how we are adding groups in
        groups = {}
        for principal in principal_type_detail_list.principals:
            if principal.principal_type == "Users":
                if principal.group_member:
                    for group in principal.group_member:
                        print(f"group_member: {principal.group_member}")
                        if group not in groups:
                            groups[group] = []
                            groups[group].append(principal.name)
                        else:
                            groups[group].append(principal.name)
        for principal in principal_type_detail_list.principals:
            if principal.principal_type == "Groups":
                for group in groups:
                    if group.lower() == principal.name.lower():
                        principal.members.extend(groups[group])
                        print(f"principal {group} has members: {groups[group]}")
        for principal in principal_type_detail_list.principals:
            print(f"Scanning {principal.principal_type}: {principal.name}")

            for policy in principal.policy_list:
                print(f"\tScanning Policy: {policy['PolicyName']}")

                if exclusions.is_policy_excluded(policy["PolicyName"]):
                    pass
                elif principal.is_principal_excluded(exclusions):
                    print(f"\tExcluded principal name: {principal.name}")
                else:
                    policy_document = policy["PolicyDocument"]
                    actions_missing_resource_constraints = []
                    for statement in policy_document.statements:
                        if modify_only:
                            if statement.effect == "Allow":
                                actions_missing_resource_constraints.extend(
                                    statement.missing_resource_constraints_for_modify_actions(
                                        exclusions
                                    )
                                )
                        else:
                            if statement.effect == "Allow":
                                actions_missing_resource_constraints.extend(
                                    statement.missing_resource_constraints(exclusions)
                                )
                    if actions_missing_resource_constraints:

                        if principal.principal_type == "User":

                            user_finding = UserFinding(
                                policy_name=policy["PolicyName"],
                                arn=principal.arn,
                                actions=actions_missing_resource_constraints,
                                policy_document=policy["PolicyDocument"],
                                exclusions=exclusions,
                                attached_managed_policies=principal.attached_managed_policies,
                                group_membership=principal.group_member,
                            )
                            self.findings.add_user_finding(user_finding)
                        elif principal.principal_type == "Group":
                            # if principal.attached_managed_policies:
                            #     for managed_policy in principal.attached_managed_policies:
                            #         logger.debug(f"The principal {principal.name} uses the managed policy {principal.attached_managed_policies}")
                            group_finding = GroupFinding(
                                policy_name=policy["PolicyName"],
                                arn=principal.arn,
                                actions=actions_missing_resource_constraints,
                                policy_document=policy["PolicyDocument"],
                                exclusions=exclusions,
                                members=principal.members,
                                attached_managed_policies=principal.attached_managed_policies,
                            )
                            # TODO: Right now I am not sure if there is tracking of group membership.
                            #  Need to figure that out.
                            self.findings.add_group_finding(group_finding)
                        elif principal.principal_type == "Role":
                            # if principal.attached_managed_policies:
                            #     logger.debug(
                            #         f"The principal {principal.name} uses the managed policy {principal.attached_managed_policies}")
                            role_finding = RoleFinding(
                                policy_name=policy["PolicyName"],
                                arn=principal.arn,
                                actions=actions_missing_resource_constraints,
                                policy_document=policy["PolicyDocument"],
                                exclusions=exclusions,
                                assume_role_policy_document=principal.assume_role_policy_document,
                                attached_managed_policies=principal.attached_managed_policies,
                            )
                            self.findings.add_role_finding(role_finding)


class PrincipalPolicyMapping:
    """Mapping between the principals and the policies assigned to them"""

    def __init__(self):
        self.entries = []

    def add_with_detail(
        self,
        principal_name,
        principal_type,
        policy_type,
        managed_by,
        policy_name,
        comment,
    ):
        """Add a new entry to the principal policy mapping"""
        entry = PrincipalPolicyMappingEntry(
            principal_name,
            principal_type,
            policy_type,
            managed_by,
            policy_name,
            comment,
        )
        self.entries.append(entry)

    def add(self, principal_policy_mapping_entry):
        """Add a new principal policy mapping entry"""
        if not isinstance(principal_policy_mapping_entry, PrincipalPolicyMappingEntry):
            raise Exception(
                "This should be the object type PrincipalPolicyMappingEntry. Please try again"
            )
        self.entries.append(principal_policy_mapping_entry)

    @property
    def json(self):
        """Return the JSON representation of the principal policy mapping"""
        entries = [x.json for x in self.entries]
        principal_policy_mapping = sorted(
            entries, key=itemgetter("Type", "Principal", "PolicyType", "PolicyName")
        )
        return principal_policy_mapping

    @property
    def users(self):
        """Return the list of users in the account"""
        result = []
        for entry in self.entries:
            if entry.principal_type == "User":
                result.append(entry)
        return result

    @property
    def groups(self):
        """Return the list of groups in the account"""
        result = []
        for entry in self.entries:
            if entry.principal_type == "Group":
                result.append(entry)
        return result

    @property
    def roles(self):
        """Return the list of roles in the account"""
        result = []
        for entry in self.entries:
            if entry.principal_type == "Role":
                result.append(entry)
        return result

    def get_post_exclusion_principal_policy_mapping(self, exclusions):
        """Given an Exclusions object, return a principal policy mapping after evaluating exclusions."""
        if not isinstance(exclusions, Exclusions):
            raise Exception(
                "The exclusions provided is not an Exclusions type object. "
                "Please supply an Exclusions object and try again."
            )
        filtered_principal_policy_mapping = PrincipalPolicyMapping()
        for user_entry in self.users:
            # If the user is explicitly mentioned in exclusions, do not add the entry
            if not user_entry.principal_name.lower() in exclusions.users:
                # If the user's policy is explicitly mentioned in exclusions, do not add the entry
                if not user_entry.policy_name.lower() in exclusions.policies:
                    # If the user is part of a group that is excluded, do not add that entry
                    if user_entry.comment:
                        for group_name in user_entry.comment:
                            if group_name.lower() not in exclusions.groups:
                                filtered_principal_policy_mapping.add(user_entry)
        for group_entry in self.groups:
            if not group_entry.principal_name.lower() in exclusions.groups:
                if not group_entry.policy_name.lower() in exclusions.policies:
                    # If we added users in the previous step that belong to this group name, then add the group
                    # Otherwise, it means that all the users in that group were excluded individually
                    # And so far, only user entries have been added to this temporary PrincipalPolicyMapping object
                    non_excluded_groups = []
                    for user_entry in filtered_principal_policy_mapping.entries:
                        if user_entry.comment:
                            for user_group_membership in user_entry.comment:
                                non_excluded_groups.append(
                                    user_group_membership.lower()
                                )
                    # if the group name is in the list of non-excluded groups
                    if group_entry.principal_name.lower() in non_excluded_groups:
                        filtered_principal_policy_mapping.add(group_entry)
        for role_entry in self.roles:
            if not role_entry.principal_name.lower() in exclusions.roles:
                if not role_entry.policy_name.lower() in exclusions.policies:
                    filtered_principal_policy_mapping.add(role_entry)
        return filtered_principal_policy_mapping


class PrincipalPolicyMappingEntry:
    """Describes the mapping between Principals and Policies.
    We use this for filtering exclusions and outputting tables of the mapping post-exclusions"""

    def __init__(
        self,
        principal_name,
        principal_type,
        policy_type,
        managed_by,
        policy_name,
        comment,
    ):
        self.principal_name = principal_name
        self.principal_type = principal_type
        self.policy_type = policy_type
        self.managed_by = managed_by
        self.policy_name = policy_name
        self.comment = comment

    @property
    def json(self):
        """Return the JSON representation of the Principal Policy mapping"""
        entry = dict(
            Principal=self.principal_name,
            Type=self.principal_type,
            PolicyType=self.policy_type,
            ManagedBy=self.managed_by,
            PolicyName=self.policy_name,
            Comment=self.comment,
        )
        return entry
