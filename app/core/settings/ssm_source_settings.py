# Standard libs
import os
from typing import Dict, Any, Type

# Non-Standard libs
from pydantic_settings import PydanticBaseSettingsSource, BaseSettings

# boto3, aws
import boto3


class SSMSettingsSource(PydanticBaseSettingsSource):
    """
    Custom Pydantic settings source to dynamically fetch configuration
    parameters from AWS Systems Manager (SSM) Parameter Store.

    This source is automatically bypassed during local development to
    prevent unneeded AWS API calls, defaulting instead to local variables.
    """
    def __init__(self, settings_cls: Type[BaseSettings]):
        super().__init__(settings_cls)
        # Initialize the AWS SSM client using system environment region fallbacks
        self.ssm = boto3.client("ssm", region_name=os.getenv("AWS_REGION", "us-east-1"))
        self.env_state = os.getenv("ENV_STATE", None)
        # Define the root path prefix used for parameter grouping in AWS SSM
        self.prefix = "/AuthService/prod/"

    def get_field_value(self, field, field_name):
        """Required override for Pydantic interface. Unused as we bulk-fetch parameters."""
        return None

    def get_parameters_from_ssm(self) -> Dict[str, Any]:
        """
        Queries AWS SSM Parameter Store recursively to collect configuration values.

        Returns:
            Dict[str, Any]: Key-value pairs matching Pydantic settings fields,
                            or an empty dictionary if local or upon AWS failure.
        """
        # Bypass remote calls if running locally or if environment state is undefined
        if self.env_state == "local" or self.env_state is None:
            return {}

        try:
            params = {}
            # Use paginator to handle pagination limits when fetching large lists of parameters
            paginator = self.ssm.get_paginator('get_parameters_by_path')

            # Request decryption automatically for secure/sensitive parameters
            for page in paginator.paginate(Path=self.prefix, WithDecryption=True):
                for p in page['Parameters']:
                    # Strip the leading hierarchy prefix to match Pydantic model field names
                    key = p['Name'].replace(self.prefix, "")
                    params[key] = p['Value']
            return params
        except Exception as e:
            # Gracefully log AWS connection issues to prevent outright application crashes
            print(f"AWS SSM Error: {e}")
            return {}

    def __call__(self) -> Dict[str, Any]:
        """Triggers the remote SSM data extraction during Pydantic initialization."""
        return self.get_parameters_from_ssm()
