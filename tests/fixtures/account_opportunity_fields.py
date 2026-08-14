"""Salesforce-like describe fixtures for Account and Opportunity."""

GENERATED_SET = frozenset({"Account", "Opportunity"})

ACCOUNT_DESCRIBE = {
    "fields": [
        {"name": "Id", "type": "id"},
        {"name": "Name", "type": "string"},
        {
            "name": "Industry",
            "type": "picklist",
            "picklistValues": [
                {"value": "Technology", "active": True},
                {"value": "Finance", "active": True},
                {"value": "Healthcare", "active": True},
                {"value": "Legacy", "active": False},
            ],
        },
        {
            "name": "OwnerId",
            "type": "reference",
            "referenceTo": ["User"],
            "relationshipName": "Owner",
        },
    ],
    "childRelationships": [
        {"relationshipName": "Opportunities", "childSObject": "Opportunity"},
    ],
}

OPPORTUNITY_DESCRIBE = {
    "fields": [
        {"name": "Id", "type": "id"},
        {"name": "Name", "type": "string"},
        {
            "name": "AccountId",
            "type": "reference",
            "referenceTo": ["Account"],
            "relationshipName": "Account",
        },
        {"name": "CloseDate", "type": "date"},
    ],
    "childRelationships": [],
}

SOBJECT_DESCRIBES = {
    "Account": ACCOUNT_DESCRIBE,
    "Opportunity": OPPORTUNITY_DESCRIBE,
}

SOBJECT_ORDER = ["Account", "Opportunity"]
