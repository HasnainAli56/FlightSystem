import requests
import logging
import os

INVENTORY_API_URL = os.getenv("INVENTORY_API_URL", "http://127.0.0.1:5001/api/tickets")

logger = logging.getLogger("external_inventory_client")
logging.basicConfig(level=logging.INFO)

class ExternalInventoryClient:
    @staticmethod
    def get_all_tickets():
        """
        Fetch all tickets from the external dummy inventory.
        Returns a list of ticket dicts or None if there was an error.
        """
        try:
            response = requests.get(INVENTORY_API_URL, timeout=3.0)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch inventory tickets. Status code: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching from external inventory API: {e}")
            return None

    @staticmethod
    def update_status(ticket_id, status, resale_price=None, seller_name=None, seller_phone=None, seller_email=None):
        """
        Update the status of a ticket in the external inventory.
        Can optionally sync resale price and seller information.
        Returns the updated ticket dictionary or None on failure.
        """
        url = f"{INVENTORY_API_URL}/{ticket_id}/status"
        payload = {"ticket_status": status}
        
        if resale_price is not None:
            payload["resale_price"] = int(resale_price)
        if seller_name:
            payload["seller_name"] = seller_name
        if seller_phone:
            payload["seller_phone"] = seller_phone
        if seller_email:
            payload["seller_email"] = seller_email

        try:
            response = requests.post(url, json=payload, timeout=3.0)
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    return result.get("ticket")
            logger.error(f"Failed to update ticket status on external inventory. Status code: {response.status_code}, response: {response.text}")
            return None
        except Exception as e:
            logger.error(f"Error updating status in external inventory API: {e}")
            return None

    @staticmethod
    def update_ticket(ticket_id, ticket_data):
        """
        Update complete ticket data in the external inventory.
        Returns the updated ticket dictionary or None on failure.
        """
        url = f"{INVENTORY_API_URL}/{ticket_id}"
        try:
            response = requests.put(url, json=ticket_data, timeout=3.0)
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    return result.get("ticket")
            logger.error(f"Failed to update ticket details on external inventory. Status code: {response.status_code}, response: {response.text}")
            return None
        except Exception as e:
            logger.error(f"Error updating ticket in external inventory API: {e}")
            return None
