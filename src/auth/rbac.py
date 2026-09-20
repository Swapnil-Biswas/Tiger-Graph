"""
Dynamic Multi-Tenant Role-Based Access Control (RBAC) & Fine-Grained Policy Authorization Matrix
(src/auth/rbac.py)

Enforces enterprise statutory access boundaries across fraud operations, AML compliance,
external audit, and regulatory bank examinations. Implements dynamic PII masking (GDPR Art. 5),
multi-tiered action authorization gates, and tenant isolation.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Set, Any, Optional, Tuple, List
import re
from fastapi import Header, HTTPException, Depends


class Role(str, Enum):
    L1_ANALYST = "L1_ANALYST"
    L2_SENIOR_INVESTIGATOR = "L2_SENIOR_INVESTIGATOR"
    AML_COMPLIANCE_OFFICER = "AML_COMPLIANCE_OFFICER"
    AUDITOR = "AUDITOR"
    REGULATOR_EXAMINER = "REGULATOR_EXAMINER"
    ADMIN_SUPERVISOR = "ADMIN_SUPERVISOR"


class Permission(str, Enum):
    CASE_READ = "CASE_READ"
    PII_READ_UNMASKED = "PII_READ_UNMASKED"
    ACTION_EXECUTE_L1 = "ACTION_EXECUTE_L1"  # VERIFY_WITH_CUSTOMER, STEP_UP_AUTH, MONITOR_CARD, WARN_CUSTOMER
    ACTION_EXECUTE_L2 = "ACTION_EXECUTE_L2"  # BLOCK_CARD, DECLINE_TRANSACTION, CREATE_CASE
    ACTION_EXECUTE_L3 = "ACTION_EXECUTE_L3"  # BLOCK_ALL_CARDS, FILE_SAR, CLOSE_NO_FRAUD
    POLICY_OVERRIDE = "POLICY_OVERRIDE"
    EVIDENCE_VAULT_AUDIT = "EVIDENCE_VAULT_AUDIT"
    REGULATORY_EXPORT = "REGULATORY_EXPORT"
    SCENARIO_SIMULATE = "SCENARIO_SIMULATE"


# Enterprise Role-to-Permission Matrix
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.L1_ANALYST: {
        Permission.CASE_READ,
        Permission.ACTION_EXECUTE_L1,
        Permission.EVIDENCE_VAULT_AUDIT,
    },
    Role.L2_SENIOR_INVESTIGATOR: {
        Permission.CASE_READ,
        Permission.PII_READ_UNMASKED,
        Permission.ACTION_EXECUTE_L1,
        Permission.ACTION_EXECUTE_L2,
        Permission.POLICY_OVERRIDE,
        Permission.EVIDENCE_VAULT_AUDIT,
        Permission.SCENARIO_SIMULATE,
    },
    Role.AML_COMPLIANCE_OFFICER: {
        Permission.CASE_READ,
        Permission.PII_READ_UNMASKED,
        Permission.ACTION_EXECUTE_L1,
        Permission.ACTION_EXECUTE_L2,
        Permission.ACTION_EXECUTE_L3,
        Permission.POLICY_OVERRIDE,
        Permission.EVIDENCE_VAULT_AUDIT,
        Permission.REGULATORY_EXPORT,
        Permission.SCENARIO_SIMULATE,
    },
    Role.AUDITOR: {
        Permission.CASE_READ,
        Permission.EVIDENCE_VAULT_AUDIT,
        Permission.REGULATORY_EXPORT,
        # Note: AUDITOR cannot see unmasked PII by default under GDPR / ISO 27001
    },
    Role.REGULATOR_EXAMINER: {
        Permission.CASE_READ,
        Permission.PII_READ_UNMASKED,
        Permission.EVIDENCE_VAULT_AUDIT,
        Permission.REGULATORY_EXPORT,
    },
    Role.ADMIN_SUPERVISOR: {
        Permission.CASE_READ,
        Permission.PII_READ_UNMASKED,
        Permission.ACTION_EXECUTE_L1,
        Permission.ACTION_EXECUTE_L2,
        Permission.ACTION_EXECUTE_L3,
        Permission.POLICY_OVERRIDE,
        Permission.EVIDENCE_VAULT_AUDIT,
        Permission.REGULATORY_EXPORT,
        Permission.SCENARIO_SIMULATE,
    },
}

# Action to Tier Mapping
ACTION_TIERS: Dict[str, Permission] = {
    "VERIFY_WITH_CUSTOMER": Permission.ACTION_EXECUTE_L1,
    "STEP_UP_AUTH": Permission.ACTION_EXECUTE_L1,
    "MONITOR_CARD": Permission.ACTION_EXECUTE_L1,
    "WARN_CUSTOMER": Permission.ACTION_EXECUTE_L1,
    "ALLOW_TRANSACTION": Permission.ACTION_EXECUTE_L1,
    "BLOCK_CARD": Permission.ACTION_EXECUTE_L2,
    "DECLINE_TRANSACTION": Permission.ACTION_EXECUTE_L2,
    "CREATE_CASE": Permission.ACTION_EXECUTE_L2,
    "BLOCK_ALL_CARDS": Permission.ACTION_EXECUTE_L3,
    "FILE_SAR": Permission.ACTION_EXECUTE_L3,
    "CLOSE_NO_FRAUD": Permission.ACTION_EXECUTE_L3,
}


@dataclass
class AuthUser:
    user_id: str
    role: Role
    department: str = "Fraud Operations"
    tenant_id: str = "default_bank_tenant"
    permissions: Set[Permission] = field(default_factory=set)

    def __post_init__(self):
        if not self.permissions:
            self.permissions = set(ROLE_PERMISSIONS.get(self.role, set()))

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions

    def can_execute_action(self, action_name: str, exposure_usd: float = 0.0) -> Tuple[bool, str]:
        """
        Validates whether the user's role has authority to execute a given action,
        enforcing both tier permissions and financial exposure gates.
        """
        required_perm = ACTION_TIERS.get(action_name)
        if not required_perm:
            # Default to L2 if unspecified
            required_perm = Permission.ACTION_EXECUTE_L2

        if not self.has_permission(required_perm):
            return False, f"Role '{self.role.value}' lacks required permission '{required_perm.value}' for action '{action_name}'."

        # Exposure authorization gates
        if exposure_usd > 10000.0 and self.role not in (Role.AML_COMPLIANCE_OFFICER, Role.ADMIN_SUPERVISOR):
            return False, f"Exposure (${exposure_usd:,.2f}) exceeds $10,000.00 threshold; requires AML_COMPLIANCE_OFFICER or ADMIN_SUPERVISOR."

        if exposure_usd > 2500.0 and self.role == Role.L1_ANALYST:
            return False, f"Exposure (${exposure_usd:,.2f}) exceeds L1 Analyst authority ($2,500.00); requires L2_SENIOR_INVESTIGATOR approval."

        return True, "Authorized"


class RBACManager:
    """Enterprise authorization and PII masking management service."""

    @staticmethod
    def mask_card_id(card_id: str) -> str:
        """Masks card ID: e.g. C12382-K1 -> C****-K1, 4111222233334444 -> 4111********4444."""
        if not card_id:
            return ""
        if "-" in card_id:
            parts = card_id.split("-")
            prefix = parts[0]
            masked_prefix = prefix[0] + "****" if len(prefix) > 1 else "****"
            return f"{masked_prefix}-{parts[1]}"
        elif len(card_id) >= 10:
            return card_id[:4] + ("*" * (len(card_id) - 8)) + card_id[-4:]
        return "****"

    @staticmethod
    def mask_email(email: str) -> str:
        """Masks email: e.g. john.doe@example.com -> j***e@example.com."""
        if not email or "@" not in email:
            return email or ""
        name, domain = email.split("@", 1)
        if len(name) <= 2:
            masked_name = name[0] + "*"
        else:
            masked_name = name[0] + ("*" * (len(name) - 2)) + name[-1]
        return f"{masked_name}@{domain}"

    @staticmethod
    def mask_customer_id(customer_id: str) -> str:
        """Masks customer ID: e.g. C12382 -> C***82."""
        if not customer_id:
            return ""
        if len(customer_id) <= 3:
            return "***"
        return customer_id[0] + ("*" * (len(customer_id) - 3)) + customer_id[-2:]


def mask_pii_dict(data: Any, user: AuthUser) -> Any:
    """
    Recursively inspects and masks sensitive PII fields (card_id, email, customer_id, entity_ids)
    if the user does not possess PII_READ_UNMASKED permission.
    """
    if user.has_permission(Permission.PII_READ_UNMASKED):
        return data

    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if "card_id" in k_lower or "cardid" in k_lower:
                if isinstance(v, list):
                    masked[k] = [RBACManager.mask_card_id(str(c)) for c in v]
                else:
                    masked[k] = RBACManager.mask_card_id(str(v))
            elif "email" in k_lower:
                if isinstance(v, list):
                    masked[k] = [RBACManager.mask_email(str(e)) for e in v]
                else:
                    masked[k] = RBACManager.mask_email(str(v))
            elif "customer_id" in k_lower or "cust_id" in k_lower:
                if isinstance(v, list):
                    masked[k] = [RBACManager.mask_customer_id(str(c)) for c in v]
                else:
                    masked[k] = RBACManager.mask_customer_id(str(v))
            elif "entity_ids" in k_lower:
                masked_list = []
                for ent in (v if isinstance(v, list) else [v]):
                    ent_s = str(ent)
                    if "-" in ent_s and ent_s.startswith("C"):
                        masked_list.append(RBACManager.mask_card_id(ent_s))
                    elif ent_s.startswith("C") and len(ent_s) >= 4:
                        masked_list.append(RBACManager.mask_customer_id(ent_s))
                    else:
                        masked_list.append(ent)
                masked[k] = masked_list if isinstance(v, list) else (masked_list[0] if masked_list else "")
            else:
                masked[k] = mask_pii_dict(v, user)
        return masked
    elif isinstance(data, list):
        return [mask_pii_dict(item, user) for item in data]
    return data


def get_current_user(
    x_user_role: Optional[str] = Header("L2_SENIOR_INVESTIGATOR"),
    x_user_id: Optional[str] = Header("analyst_default"),
    x_tenant_id: Optional[str] = Header("default_bank_tenant"),
) -> AuthUser:
    """
    FastAPI dependency extracting user credentials and role from request headers.
    Defaults to L2_SENIOR_INVESTIGATOR for backwards compatibility.
    """
    role_str = (x_user_role or "L2_SENIOR_INVESTIGATOR").strip().upper()
    try:
        role = Role(role_str)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user role '{role_str}'. Allowed roles: {[r.value for r in Role]}",
        )

    return AuthUser(
        user_id=x_user_id or "unknown_user",
        role=role,
        tenant_id=x_tenant_id or "default_bank_tenant",
    )


def require_permission(permission: Permission):
    """
    FastAPI dependency factory enforcing that the authenticated user possesses the required permission.
    """
    def _perm_checker(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=403,
                detail=f"Access Denied: Role '{user.role.value}' does not possess required permission '{permission.value}'.",
            )
        return user

    return _perm_checker
