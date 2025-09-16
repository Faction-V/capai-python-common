import logging
import requests
from typing import Optional
from sentry_sdk import capture_exception
from ..logging import logger as default_logger


class CollectionNotFoundException(Exception):
    """Exception raised when a collection is not found (404)."""

    pass


class QdrantService:
    def __init__(self, base_url: str, logger: Optional[logging.Logger] = None):
        self.base_url = base_url
        self.logger = logger or default_logger

    def create_qdrant_collection(
        self,
        collection_name: str,
        shard_count: int = 6,
        embedding_dimension: int = 1024,
        distance_metric: str = "COSINE",
        strict_mode_enabled: bool = False,
        replication_factor: int = 2,
        write_consistency_factor: int = 2,
        platform_cluster_id: Optional[str] = None,
        orgid: Optional[str] = None,
    ) -> dict:
        """
        Create a new Qdrant collection.

        Args:
            collection_name: Name of the collection to create
            shard_count: Number of shards for the collection (default: 6)
            embedding_dimension: Dimension of the embedding vectors (default: 1024)
            distance_metric: Distance metric for vector similarity (COSINE, DOT, or EUCLID)
            strict_mode_enabled: Whether to enable strict mode for updates (default: False)
            platform_cluster_id: Optional ID of the dedicated Qdrant cluster
            orgid: Optional organization ID for dedicated clusters

        Returns:
            dict: Response from the Qdrant service API
        """
        endpoint = f"{self.base_url}/create-collection"

        # Prepare the request parameters
        params = {
            "collection_name": collection_name,
            "shard_count": shard_count,
            "embedding_dimension": embedding_dimension,
            "distance_metric": distance_metric,
            "strict_mode_enabled": strict_mode_enabled,
            "replication_factor": replication_factor,
            "write_consistency_factor": write_consistency_factor,
        }

        # Add optional parameters for dedicated clusters if provided
        if platform_cluster_id:
            params["platform_cluster_id"] = platform_cluster_id

        if orgid:
            params["orgid"] = orgid

        try:
            # Make the POST request to the qdrant-svc API
            response = requests.post(endpoint, params=params)
            response.raise_for_status()  # Raise an exception for HTTP errors

            return response.json()
        except requests.exceptions.RequestException as e:
            capture_exception(e)
            self.logger.error(f"Error creating Qdrant collection: {str(e)}")
            raise Exception(f"Failed to create Qdrant collection: {str(e)}")
        except Exception as e:
            capture_exception(e)
            self.logger.error(f"Unexpected error creating Qdrant collection: {str(e)}")
            raise Exception(f"Unexpected error creating Qdrant collection: {str(e)}")

    def delete_points_by_external_id(
        self,
        external_id: str,
        collection_name: str,
        platform_cluster_id: Optional[str] = None,
        orgid: Optional[str] = None,
    ) -> dict:
        """
        Delete points from a Qdrant collection by external ID.

        Args:
            external_id: The external ID of the points to delete.

        Returns:
            dict: Response from the Qdrant service API
        """
        endpoint = f"{self.base_url}/delete-by-external-id"

        # Prepare the request parameters
        params = {
            "collection_name": collection_name,
            "external_id": external_id,
        }

        # Add optional parameters for dedicated clusters if provided
        if platform_cluster_id:
            params["platform_cluster_id"] = platform_cluster_id

        if orgid:
            params["orgid"] = orgid

        try:
            # Make the DELETE request to the qdrant-svc API
            response = requests.delete(endpoint, params=params)
            response.raise_for_status()  # Raise an exception for HTTP errors

            return response.json()
        except requests.exceptions.RequestException as e:
            capture_exception(e)
            self.logger.error(
                f"Error deleting Qdrant points for external_id {external_id}: {str(e)}"
            )
            raise Exception(
                f"Failed to delete Qdrant points for external_id {external_id}: {str(e)}"
            )
        except Exception as e:
            capture_exception(e)
            self.logger.error(
                f"Unexpected error deleting Qdrant points for external_id {external_id}: {str(e)}"
            )
            raise Exception(
                f"Unexpected error deleting Qdrant points for external_id {external_id}: {str(e)}"
            )

    def delete_qdrant_collection(
        self, collection_name: str, orgid: str = None, cluster_id: str = None
    ) -> dict:
        """
        Delete a Qdrant collection.

        Args:
            collection_name: Name of the collection to delete

        Returns:
            dict: Response from the Qdrant service API
        """
        endpoint = f"{self.base_url}/delete-collection"

        try:
            # Make the DELETE request to the qdrant-svc API
            response = requests.delete(
                endpoint,
                params={
                    "collection_name": collection_name,
                    "platform_cluster_id": cluster_id,
                    "orgid": orgid,
                },
            )
            response.raise_for_status()  # Raise an exception for HTTP errors

            return response.json()
        except requests.exceptions.RequestException as e:
            capture_exception(e)
            self.logger.error(f"Error deleting Qdrant collection: {str(e)}")
            raise Exception(f"Failed to delete Qdrant collection: {str(e)}")
        except Exception as e:
            capture_exception(e)
            self.logger.error(f"Unexpected error deleting Qdrant collection: {str(e)}")
            raise Exception(f"Unexpected error deleting Qdrant collection: {str(e)}")

    def collection_info(
        self,
        collection_name: str,
        orgid: Optional[str] = None,
        cluster_id: Optional[str] = None,
    ) -> dict:
        """
        Get information about a Qdrant collection.

        Args:
            collection_name: Name of the collection to get info for

        Returns:
            dict: Response from the Qdrant service API

        Raises:
            CollectionNotFoundException: If the collection does not exist (404)
            Exception: For other request errors
        """
        endpoint = f"{self.base_url}/collection-info"

        try:
            response = requests.get(
                endpoint,
                params={
                    "collection_name": collection_name,
                    "platform_cluster_id": cluster_id,
                    "orgid": orgid,
                },
            )
            response.raise_for_status()  # Raise an exception for HTTP errors

            return response.json()
        except requests.exceptions.HTTPError as e:
            capture_exception(e)
            if e.response.status_code == 404:
                self.logger.warning(f"Collection not found: {collection_name}")
                raise CollectionNotFoundException(
                    f"Collection '{collection_name}' not found"
                )
            else:
                self.logger.error(
                    f"HTTP error getting Qdrant collection info: {str(e)}"
                )
                raise Exception(f"Failed to get Qdrant collection info: {str(e)}")
        except requests.exceptions.RequestException as e:
            capture_exception(e)
            self.logger.error(f"Error getting Qdrant collection info: {str(e)}")
            raise Exception(f"Failed to get Qdrant collection info: {str(e)}")
        except Exception as e:
            capture_exception(e)
            self.logger.error(
                f"Unexpected error getting Qdrant collection info: {str(e)}"
            )
            raise Exception(
                f"Unexpected error getting Qdrant collection info: {str(e)}"
            )
