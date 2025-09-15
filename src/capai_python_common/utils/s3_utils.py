import boto3
from botocore.exceptions import ClientError
import logging
import os
from typing import Optional
from sentry_sdk import capture_exception
import arrow
from ..logging import logger as default_logger


class s3Client:
    def __init__(self, bucket: str, logger: Optional[logging.Logger] = None):
        self.bucket = bucket
        self.total = 0
        self.uploaded = 0
        self.s3 = boto3.client("s3")
        self.logger = logger or default_logger
        self.PYTHON_MAGIC_AVAILABLE = False
        try:
            import magic

            self.magic_lib = magic
            self.PYTHON_MAGIC_AVAILABLE = True
        except ImportError as e:
            default_logger.warning(
                f"{str(e)}.  You might be missing `apt install libmagic-dev?`"
            )

    def exists_in_s3(self, key):
        try:
            s3obj = self.s3.head_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            else:
                raise
        return s3obj

    def empty_bucket(self):
        """
        Caution!! Empties all objects from the bucket.
        """
        # Create an S3 resource and use it to delete all objects in the bucket
        s3_resource = boto3.resource("s3")
        bucket = s3_resource.Bucket(self.bucket)
        bucket.objects.all().delete()

    def upload_callback(self, size):
        if self.total == 0:
            return
        self.uploaded += size
        # self.logger.debug("{} %".format(int(self.uploaded / self.total * 100)))

    def upload(self, key, file, content_type=None, metadata=None, tags=None):
        """
        Upload a file to S3 with optional content type, metadata, and tags

        Args:
            key (str): S3 object key
            file (str): Path to the file to upload
            content_type (str, optional): Content type of the file. If None, auto-detected.
            metadata (dict, optional): Metadata to attach to the S3 object
            tags (list, optional): List of dictionaries with 'Key' and 'Value' keys for S3 object tags
                                  Example: [{'Key': 'project', 'Value': 'demo'}, {'Key': 'env', 'Value': 'dev'}]

        Returns:
            bool: True if successful
        """
        self.total = os.stat(file).st_size
        if content_type is None and self.PYTHON_MAGIC_AVAILABLE:
            mime = self.magic_lib.Magic(mime=True)
            content_type = mime.from_file(file)

        extra_args = {"ContentType": content_type}
        if metadata:
            extra_args["Metadata"] = metadata

        # Add tags if provided
        if tags:
            # Convert tags list to the format required by S3 (URL-encoded string)
            tag_string = "&".join([f"{tag['Key']}={tag['Value']}" for tag in tags])
            extra_args["Tagging"] = tag_string

        with open(file, "rb") as data:
            self.s3.upload_fileobj(
                data,
                self.bucket,
                key,
                Callback=self.upload_callback,
                ExtraArgs=extra_args,
            )
        return True

    def download(self, key: str, download_path: str = "/tmp"):
        """
        Download a file from S3 to a local path

        Args:
            key (str): S3 object key
            download_path (str): Local path to download the file to

        Returns:
            str: Path to the downloaded file
        """
        exists = self.exists_in_s3(key)
        if not exists:
            raise FileNotFoundError(
                f"S3 object with key '{key}' not found in bucket '{self.bucket}'"
            )

        # Extract filename from key
        filename = key.split("/")[-1] if "/" in key else key

        # Create the full local file path
        local_file_path = os.path.join(download_path, filename)

        try:
            # Ensure the download directory exists
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

            # Download the file
            self.s3.download_file(Bucket=self.bucket, Key=key, Filename=local_file_path)

            return local_file_path

        except ClientError as e:
            capture_exception(e)
            raise

    def create_presigned_url(self, object_key, expiration=3600, download: bool = False):
        """Generate a presigned URL to share an S3 object
        https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html

        :param object_key: string
        :param expiration: Time in seconds for the presigned URL to remain valid
        :param download: If True, sets the Content-Disposition header to attachment for file download
        :return: Presigned URL as string. If error, returns None.
        """

        # Generate a presigned URL for the S3 object
        params = {
            "Bucket": self.bucket,
            "Key": object_key,
        }
        if download:
            params["ResponseContentDisposition"] = "attachment"
        try:
            response = self.s3.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expiration,
            )
        except ClientError as e:
            logging.error(e)
            return None

        # The response contains the presigned URL
        return response

    def list_objects(self, prefix=""):
        """
        List objects in the S3 bucket with optional prefix filtering

        Args:
            prefix (str): Prefix to filter objects (e.g., "orgid/collection/")

        Returns:
            list: List of object metadata dictionaries
        """
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix)

            objects = []
            if "Contents" in response:
                for obj in response["Contents"]:
                    # Get additional metadata for each object
                    try:
                        head_response = self.s3.head_object(
                            Bucket=self.bucket, Key=obj["Key"]
                        )
                        content_type = head_response.get("ContentType", "unknown")
                        custom_metadata = head_response.get("Metadata", {})
                    except ClientError:
                        content_type = "unknown"
                        custom_metadata = {}

                    # Extract filename from key
                    filename = (
                        obj["Key"].split("/")[-1] if "/" in obj["Key"] else obj["Key"]
                    )
                    if filename == ".collection_info":
                        continue

                    # Get object tags
                    tags = {}
                    try:
                        tag_response = self.s3.get_object_tagging(
                            Bucket=self.bucket, Key=obj["Key"]
                        )
                        if "TagSet" in tag_response:
                            tags = {
                                tag["Key"]: tag["Value"]
                                for tag in tag_response["TagSet"]
                            }
                    except ClientError as e:
                        self.logger.warning(
                            f"Error getting tags for object {obj['Key']}: {e}"
                        )

                    objects.append(
                        {
                            "key": obj["Key"],
                            "filename": filename,
                            "size": obj["Size"],
                            "size_mb": round(obj["Size"] / 1024 / 1024, 2),
                            "last_modified": obj["LastModified"].isoformat(),
                            "content_type": content_type,
                            "metadata": custom_metadata,
                            "upload_timestamp": custom_metadata.get("upload-timestamp"),
                            "s3_url": f"s3://{self.bucket}/{obj['Key']}",
                            "tags": tags,
                        }
                    )

            return objects

        except ClientError as e:
            self.logger.error(f"Error listing objects: {e}")
            raise

    def delete_object(self, key):
        """
        Delete an object from the S3 bucket

        Args:
            key (str): S3 object key to delete

        Returns:
            bool: True if successful
        """
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=key)
            self.logger.info(f"Successfully deleted object: {key}")
            return True
        except ClientError as e:
            self.logger.error(f"Error deleting object {key}: {e}")
            raise

    def create_collection(self, orgid, collection) -> str:
        """
        Create a collection (directory) by uploading a placeholder file

        Args:
            orgid (str): Organization ID
            collection (str): Collection name

        Returns:
            bool: True if successful
        """
        try:
            # Create a placeholder file to establish the directory structure
            collection_prefix = f"{orgid}/{collection.lower()}"
            placeholder_key = f"{collection_prefix}/.collection_info"
            placeholder_content = f"Collection: {collection}\nCreated: {arrow.utcnow().isoformat()}\nOrganization: {orgid}"

            # Upload placeholder content
            self.s3.put_object(
                Bucket=self.bucket,
                Key=placeholder_key,
                Body=placeholder_content.encode("utf-8"),
                ContentType="text/plain",
                Metadata={
                    "collection-name": collection,
                    "organization-id": orgid,
                    "created-timestamp": arrow.utcnow().isoformat(),
                    "type": "collection-info",
                },
            )

            self.logger.info(f"Successfully created collection: {orgid}/{collection}")
            return collection_prefix
        except ClientError as e:
            self.logger.error(f"Error creating collection {orgid}/{collection}: {e}")
            raise

    def delete_collection(self, s3_prefix: str) -> dict:
        """
        Delete an entire collection (directory) and all its contents

        Args:
            s3_prefix (str): S3 prefix for the collection

        Returns:
            dict: Summary of deletion operation
        """
        try:
            # List all objects in the collection
            response = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=s3_prefix)

            deleted_objects = []
            if "Contents" in response:
                # Delete all objects in the collection
                objects_to_delete = [
                    {"Key": obj["Key"]} for obj in response["Contents"]
                ]

                if objects_to_delete:
                    delete_response = self.s3.delete_objects(
                        Bucket=self.bucket, Delete={"Objects": objects_to_delete}
                    )

                    deleted_objects = [
                        obj["Key"] for obj in delete_response.get("Deleted", [])
                    ]

            self.logger.info(
                f"Successfully deleted collection: {s3_prefix} ({len(deleted_objects)} objects)"
            )
            return {
                "s3_prefix": s3_prefix,
                "deleted_objects": deleted_objects,
                "total_deleted": len(deleted_objects),
            }

        except ClientError as e:
            self.logger.error(f"Error deleting collection {s3_prefix}: {e}")
            raise

    def list_collections(self, orgid):
        """
        List all collections for an organization

        Args:
            orgid (str): Organization ID

        Returns:
            list: List of collection names
        """
        try:
            prefix = f"{orgid}/"
            response = self.s3.list_objects_v2(
                Bucket=self.bucket, Prefix=prefix, Delimiter="/"
            )

            collections = []
            if "CommonPrefixes" in response:
                for prefix_info in response["CommonPrefixes"]:
                    # Extract collection name from prefix
                    collection_path = prefix_info["Prefix"]
                    collection_name = collection_path.rstrip("/").split("/")[-1]
                    collections.append(collection_name)

            return collections

        except ClientError as e:
            self.logger.error(f"Error listing collections for {orgid}: {e}")
            raise

    def get_tags(self, key):
        """
        Get tags for an S3 object

        Args:
            key (str): S3 object key

        Returns:
            dict: Dictionary of tags with 'Key' and 'Value'
        """
        try:
            response = self.s3.get_object_tagging(Bucket=self.bucket, Key=key)
            return {tag["Key"]: tag["Value"] for tag in response.get("TagSet", [])}
        except ClientError as e:
            self.logger.error(f"Error getting tags for object {key}: {e}")
            raise

    def put_tags(self, key, tags):
        """
        Set tags on an S3 object, replacing any existing tags

        Args:
            key (str): S3 object key
            tags (list): List of dictionaries with 'Key' and 'Value' keys for S3 object tags
                        Example: [{'Key': 'project', 'Value': 'demo'}, {'Key': 'env', 'Value': 'dev'}]

        Returns:
            bool: True if successful
        """
        try:
            self.s3.put_object_tagging(
                Bucket=self.bucket, Key=key, Tagging={"TagSet": tags}
            )
            self.logger.info(f"Successfully set tags on object: {key}")
            return True
        except ClientError as e:
            self.logger.error(f"Error setting tags on object {key}: {e}")
            raise

    def append_tags(self, key, new_tags, exclude_keys=None):
        """
        Add new tags to an S3 object while preserving existing tags

        When a tag with the same key already exists in the S3 object, this method will:
        1. Remove the existing tag with that key
        2. Add the new tag with the same key but updated value
        This ensures tag keys remain unique in the final set and new values take precedence.

        Args:
            key (str): S3 object key
            new_tags (list): List of dictionaries with 'Key' and 'Value' keys for new S3 object tags
            exclude_keys (list, optional): List of tag keys to exclude from existing tags before merging

        Returns:
            bool: True if successful

        Raises:
            ValueError: If the total number of tags would exceed the AWS limit of 10 tags per object
        """
        try:
            # Get existing tags
            try:
                existing_tag_response = self.s3.get_object_tagging(
                    Bucket=self.bucket, Key=key
                )
                existing_tags = existing_tag_response.get("TagSet", [])

                # Filter out excluded keys if provided
                if exclude_keys:
                    existing_tags = [
                        tag for tag in existing_tags if tag["Key"] not in exclude_keys
                    ]

                # Filter out keys that will be updated by new_tags
                new_tag_keys = [tag["Key"] for tag in new_tags]
                existing_tags = [
                    tag for tag in existing_tags if tag["Key"] not in new_tag_keys
                ]

                # Combine existing and new tags
                updated_tags = existing_tags + new_tags

                # Check if the total number of tags exceeds the AWS limit of 10
                if len(updated_tags) > 10:
                    error_msg = f"Total number of tags ({len(updated_tags)}) would exceed AWS limit of 10 tags per object for {key}"
                    self.logger.error(error_msg)
                    raise ValueError(error_msg)

            except ClientError as tag_error:
                self.logger.warning(
                    f"Error getting existing tags for {key}: {str(tag_error)}. Using only new tags."
                )
                updated_tags = new_tags

                # Still check the limit even if we're only using new tags
                if len(updated_tags) > 10:
                    error_msg = f"Total number of tags ({len(updated_tags)}) would exceed AWS limit of 10 tags per object for {key}"
                    self.logger.error(error_msg)
                    raise ValueError(error_msg)

            # Update object with combined tags
            self.s3.put_object_tagging(
                Bucket=self.bucket, Key=key, Tagging={"TagSet": updated_tags}
            )

            self.logger.info(f"Successfully appended tags to object: {key}")
            return True

        except ClientError as e:
            self.logger.error(f"Error appending tags to object {key}: {e}")
            raise
