"""
AWS SSM Parameter Store client for secure parameter management.
"""

import os
import boto3
from botocore.exceptions import ClientError
import logging
from sentry_sdk import capture_exception
from typing import Optional
from ..logging import logger as default_logger


class SSMClient:
    """
    A client for interacting with AWS SSM Parameter Store.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the SSM client.
        """
        self.client = boto3.client("ssm", region_name=os.environ.get("AWS_REGION"))
        self.logger = logger or default_logger

    def create_secure_parameter(
        self, name: str, value: str, description: str = ""
    ) -> str:
        """
        Create a new secure parameter in SSM Parameter Store.

        Args:
            name (str): The name of the parameter
            value (str): The value to be stored securely
            description (str, optional): Description of the parameter

        Returns:
            str: The name of the parameter or a constructed ARN
        """
        try:
            response = self.client.put_parameter(
                Name=name,
                Value=value,
                Type="SecureString",
                Description=description,
                Overwrite=True,
            )

            # Try to get the ARN from describe_parameters, but handle empty results
            try:
                param_info = self.client.describe_parameters(
                    Filters=[{"Key": "Name", "Values": [name]}]
                )

                if param_info.get("Parameters") and len(param_info["Parameters"]) > 0:
                    return param_info["Parameters"][0].get("ARN", name)
                else:
                    # If we can't get the ARN, construct a pseudo-ARN using the name
                    self.logger.warning(
                        f"Could not retrieve ARN for parameter {name}, using name as identifier"
                    )
                    return name
            except Exception as e:
                self.logger.warning(f"Error retrieving parameter ARN: {e}")
                return name

        except ClientError as e:
            capture_exception(e)
            self.logger.error(f"Error creating secure parameter: {e}")
            raise e

    def get_secure_parameter(self, name_or_arn: str) -> str | None:
        """
        Retrieve a secure parameter from SSM Parameter Store.

        Args:
            name_or_arn (str): The name or ARN of the parameter

        Returns:
            Optional[str]: The decrypted parameter value, or None if not found
        """
        try:
            # Extract parameter name from ARN if it's an ARN
            if name_or_arn.startswith("arn:aws:ssm:"):
                # Get everything after "parameter"
                parts = name_or_arn.split(":")
                if len(parts) >= 6:
                    # The parameter path is in the 6th part, after "parameter"
                    parameter_path = parts[5]
                    if parameter_path.startswith("parameter"):
                        parameter_name = parameter_path
                    else:
                        parameter_name = f"/{parameter_path}"
                else:
                    self.logger.error(f"Invalid ARN format: {name_or_arn}")
                    return None
            else:
                # If not an ARN, use as is
                parameter_name = name_or_arn

            self.logger.debug(f"Getting parameter: {parameter_name}")
            response = self.client.get_parameter(
                Name=parameter_name, WithDecryption=True
            )
            return response["Parameter"]["Value"]
        except self.client.exceptions.ParameterNotFound:
            self.logger.warning(f"Parameter not found: {name_or_arn}")
            return None
        except Exception as e:
            capture_exception(e)
            self.logger.error(f"Error getting parameter: {e}")
            return None

    def delete_parameter(self, arn: str) -> bool:
        """
        Delete a parameter from SSM Parameter Store.
        Note: We store the ARN but the actual operation is done using the parameter name.
        Args:
            arn (str): The ARN of the parameter to delete

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            # Extract parameter name from ARN
            # ARN format: arn:aws:ssm:region:account-id:parameter/path/to/parameter
            if arn.startswith("arn:aws:ssm:"):
                # Get everything after "parameter"
                parts = arn.split(":")
                if len(parts) >= 6:
                    # The parameter path is in the 6th part, after "parameter"
                    parameter_path = parts[5]
                    if parameter_path.startswith("parameter"):
                        parameter_name = parameter_path
                    else:
                        parameter_name = f"/{parameter_path}"
                else:
                    self.logger.error(f"Invalid ARN format: {arn}")
                    return False
            else:
                # If not an ARN, use as is (for backward compatibility)
                parameter_name = arn

            self.logger.debug(f"Deleting parameter: {parameter_name}")
            self.client.delete_parameter(Name=parameter_name)
            return True
        except Exception as e:
            capture_exception(e)
            self.logger.error(f"Error deleting parameter: {e}")
            return False

    def update_parameter(self, arn: str, value: str, description: str = "") -> bool:
        """
        Update an existing secure parameter.
        Note: We store the ARN but the actual operation is done using the parameter name.
        Args:
            arn (str): The ARN of the parameter to delete
            value (str): The new value to be stored
            description (str, optional): Updated description

        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Extract parameter name from ARN
            # ARN format: arn:aws:ssm:region:account-id:parameter/path/to/parameter
            if arn.startswith("arn:aws:ssm:"):
                # Get everything after "parameter"
                parts = arn.split(":")
                if len(parts) >= 6:
                    # The parameter path is in the 6th part, after "parameter"
                    parameter_path = parts[5]
                    if parameter_path.startswith("parameter"):
                        parameter_name = parameter_path
                    else:
                        parameter_name = f"/{parameter_path}"
                else:
                    self.logger.error(f"Invalid ARN format: {arn}")
                    return False
            else:
                # If not an ARN, use as is (for backward compatibility)
                parameter_name = arn

            self.logger.debug(f"Updating parameter: {parameter_name}")
            self.client.put_parameter(
                Name=parameter_name,
                Value=value,
                Type="SecureString",
                Description=description,
                Overwrite=True,
            )
            return True
        except Exception as e:
            capture_exception(e)
            self.logger.error(f"Error updating parameter: {e}")
            return False
