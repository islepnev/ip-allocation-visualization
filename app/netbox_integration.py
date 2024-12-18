# app/netbox_integration.py

import logging
import os
from dotenv import load_dotenv

from pynetbox.core.api import Api

class NetboxAddressManager:

    def __init__(self, api_url: str = None, api_token: str = None):
        """
        Initializes NetBox address manager by connecting to the API and fetching data.
        :param api_url: URL for the NetBox API.
        :param api_token: Token for authentication with the NetBox API.
        """
        self.nb = self.nb_connect(api_url, api_token)
        self.prefixes = self._fetch_data(self.nb.ipam.prefixes.all, "prefixes")
        self.ip_addresses = self._fetch_data(self.nb.ipam.ip_addresses.all, "IP addresses")
        self.tenants_list = self._fetch_data(self.nb.tenancy.tenants.all, "tenants")
        self.tenants = {item["id"]: item for item in self.tenants_list}
        self.vrf_list = self._fetch_data(self.nb.ipam.vrfs.all, "vrfs")
        self.vrfs = {item["id"]: item for item in self.vrf_list}

    @staticmethod
    def nb_connect(api_url: str = None, api_token: str = None) -> Api:
        """
        Connect to the NetBox API using provided credentials or environment variables.
        :param api_url: URL for the NetBox API.
        :param api_token: Token for authentication with the NetBox API.
        :return: An instance of the NetBox API.
        """
        if not api_url or not api_token:
            load_dotenv()
            api_url = api_url or os.getenv('NETBOX_API_URL')
            api_token = api_token or os.getenv('NETBOX_API_TOKEN')

        if not api_url or not api_token:
            raise ValueError("NetBox API URL and token must be provided.")
        
        return Api(api_url, token=api_token)

    @staticmethod
    def _fetch_data(fetch_method, data_type: str) -> list:
        """
        Fetch and serialize data from the NetBox API.
        :param fetch_method: The API method to fetch data.
        :param data_type: Description of the data type being fetched (for logging purposes).
        :return: A list of serialized data.
        """
        try:
            data = [item.serialize() for item in fetch_method()]
            logging.info(f"Loaded {len(data)} {data_type} from NetBox")
            return data
        except Exception as e:
            logging.error(f"Error fetching {data_type} from NetBox: {e}")
            raise RuntimeError(f"Failed to fetch {data_type} from NetBox")

    def get_prefixes(self) -> list:
        return self.prefixes

    def get_ip_addresses(self) -> list:
        return self.ip_addresses

    def get_vrfs(self) -> list:
        return self.vrf_list

    def get_tenant(self, tenant_id):
        return self.tenants.get(tenant_id)
