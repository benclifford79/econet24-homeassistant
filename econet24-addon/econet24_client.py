"""
Econet24.com Cloud API Client

This module provides a Python client for accessing HVAC data from econet24.com.
Based on reverse engineering of the web interface and existing community work.

Usage:
    client = Econet24Client()
    client.login("your_email@example.com", "your_password")
    devices = client.get_devices()
    data = client.get_current_params(device_uid)
"""

import os
import re
import requests
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

# Get log level from environment (set by bridge or run.sh)
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("econet24_client")


class Econet24Error(Exception):
    """Base exception for Econet24 client errors."""
    pass


class LoginError(Econet24Error):
    """Raised when login fails."""
    pass


class SessionExpiredError(Econet24Error):
    """Raised when session has expired."""
    pass


class Econet24Client:
    """Client for econet24.com cloud API."""

    API_BASE = "https://www.econet24.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self._devices: list = []
        self._logged_in = False
        self._device_uid_from_redirect: str = None

    def _get(self, path: str, **kwargs) -> requests.Response:
        """Make a GET request to the API."""
        url = f"{self.API_BASE}{path}"
        logger.debug(f"GET {url}")
        response = self.session.get(url, **kwargs)
        logger.debug(f"Response status: {response.status_code}")
        return response

    def _post(self, path: str, **kwargs) -> requests.Response:
        """Make a POST request to the API."""
        url = f"{self.API_BASE}{path}"
        logger.debug(f"POST {url}")
        response = self.session.post(url, **kwargs)
        logger.debug(f"Response status: {response.status_code}")
        return response

    def _ensure_logged_in(self):
        """Check that we have a valid session."""
        if not self._logged_in:
            raise SessionExpiredError("Not logged in. Call login() first.")
        # Check for their custom session cookies
        has_session = (
            "_mlmsc" in self.session.cookies or
            "_mlmlc" in self.session.cookies or
            "sessionid" in self.session.cookies
        )
        if not has_session:
            raise SessionExpiredError("Session cookie missing. Need to re-login.")

    def login(self, username: str, password: str) -> bool:
        """
        Login to econet24.com.

        Args:
            username: Your econet24.com email address
            password: Your econet24.com password

        Returns:
            True if login successful

        Raises:
            LoginError: If login fails
        """
        # First, get the login page to establish CSRF cookie
        self._get("/login/")

        # Get CSRF token from cookie
        csrf_token = self.session.cookies.get("csrftoken")
        if not csrf_token:
            raise LoginError("Could not get CSRF token from login page")

        logger.debug(f"Got CSRF token: {csrf_token}")

        # Attempt login with CSRF token
        response = self._post(
            "/login/",
            data={
                "username": username,
                "password": password,
                "csrfmiddlewaretoken": csrf_token,
            },
            headers={
                "X-CSRFToken": csrf_token,
                "Referer": f"{self.API_BASE}/login/",
                "Origin": self.API_BASE,
            },
            allow_redirects=True
        )

        # Debug login response
        logger.debug(f"Response URL: {response.url}")
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Cookies after login: {dict(self.session.cookies)}")

        # Check for error in response (Django often returns to login page with error)
        if "/login" in response.url and response.status_code == 200:
            # Might still be on login page - check for error message
            if "error" in response.text.lower() or "invalid" in response.text.lower():
                logger.error("Login rejected - check credentials")
                raise LoginError("Invalid username or password")

        # Check if login succeeded by looking at redirect URL
        # Successful login redirects to /view/device/{UID}/main/
        device_match = re.search(r'/view/device/([A-Z0-9]+)/', response.url)
        if device_match:
            self._device_uid_from_redirect = device_match.group(1)
            logger.info(f"Login successful - found device UID: {self._device_uid_from_redirect}")
            self._logged_in = True
            self._devices = [self._device_uid_from_redirect]
        elif "_mlmsc" in self.session.cookies or "_mlmlc" in self.session.cookies:
            # Alternative: check for their custom session cookies
            logger.info("Login successful (session cookies set)")
            self._logged_in = True
        else:
            logger.error("Login may have failed - no device redirect or session cookies")
            logger.debug(f"Cookies: {dict(self.session.cookies)}")
            logger.debug(f"Response URL: {response.url}")
            raise LoginError("Login failed - could not verify session")

        # Try to fetch devices list
        try:
            devices_from_api = self.get_user_devices()
            if devices_from_api:
                self._devices = devices_from_api
        except Exception as e:
            logger.debug(f"Could not fetch devices from API: {e}")
            # Keep the device from redirect if we have it

        logger.info(f"Found {len(self._devices)} device(s): {self._devices}")

        return True

    def get_devices(self) -> list:
        """
        Get all devices (admin endpoint).

        Returns:
            List of device information
        """
        self._ensure_logged_in()
        response = self._get("/service/getDevices")
        response.raise_for_status()
        return response.json()

    def get_user_devices(self) -> list:
        """
        Get devices associated with the logged-in user.

        Returns:
            List of device UIDs
        """
        self._ensure_logged_in()
        response = self._get("/service/getUserDevices")
        response.raise_for_status()
        data = response.json()
        return data.get("devices", [])

    def get_device_info(self, uid: str = None) -> dict:
        """
        Get detailed device information.

        Args:
            uid: Device UID (uses first device if not specified)

        Returns:
            Device information dict
        """
        self._ensure_logged_in()
        if uid is None:
            if not self._devices:
                raise Econet24Error("No devices available")
            uid = self._devices[0]

        # Try various endpoint patterns that might return device info
        endpoints_to_try = [
            f"/service/getDeviceInfo?uid={uid}",
            f"/service/getDevice?uid={uid}",
            f"/service/getSysParams?uid={uid}",
        ]

        for endpoint in endpoints_to_try:
            try:
                response = self._get(endpoint)
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        logger.info(f"Found device info at {endpoint}")
                        return data
            except Exception as e:
                logger.debug(f"Endpoint {endpoint} failed: {e}")

        return {}

    def get_device_params(self, uid: str = None) -> dict:
        """
        Get all device parameters including current sensor values.

        This is the main endpoint for getting live data from the device.

        Args:
            uid: Device UID (uses first device if not specified)

        Returns:
            Dict containing:
                - uid: Device UID
                - curr: Current sensor values
                - currUnits: Units for each parameter
                - currNumbers: Numeric identifiers
                - schemaParams: Schema/config info
                - tilesParams: UI tile configuration
                - wifiQuality/wifiStrength: Network status
                - Various version numbers
        """
        self._ensure_logged_in()
        if uid is None:
            if not self._devices:
                raise Econet24Error("No devices available")
            uid = self._devices[0]

        response = self._get(f"/service/getDeviceParams?uid={uid}")
        response.raise_for_status()
        return response.json()

    def get_current_values(self, uid: str = None) -> dict:
        """
        Get just the current sensor values (convenience method).

        Args:
            uid: Device UID (uses first device if not specified)

        Returns:
            Dict of parameter_name -> current_value
        """
        data = self.get_device_params(uid)
        return data.get("curr", {})

    def get_current_with_units(self, uid: str = None) -> dict:
        """
        Get current values with their units.

        Args:
            uid: Device UID (uses first device if not specified)

        Returns:
            Dict of parameter_name -> {"value": x, "unit": y}
        """
        data = self.get_device_params(uid)
        curr = data.get("curr", {})
        units = data.get("currUnits", {})

        result = {}
        for key, value in curr.items():
            result[key] = {
                "value": value,
                "unit": units.get(key, "")
            }
        return result

    def get_current_params(self, uid: str = None) -> dict:
        """
        DEPRECATED: Use get_device_params() instead.

        Get current parameters/sensor values for a device.
        """
        return {"device_params": self.get_device_params(uid)}

    def get_history(
        self,
        uid: str = None,
        start: datetime = None,
        end: datetime = None
    ) -> dict:
        """
        Get historical parameter values.

        Args:
            uid: Device UID (uses first device if not specified)
            start: Start datetime (defaults to start of today)
            end: End datetime (defaults to now)

        Returns:
            Historical data dict
        """
        self._ensure_logged_in()
        if uid is None:
            if not self._devices:
                raise Econet24Error("No devices available")
            uid = self._devices[0]

        if end is None:
            end = datetime.now()
        if start is None:
            start = datetime(end.year, end.month, end.day, 0, 0, 0)

        response = self._get(
            "/service/getHistoryParamsValues",
            params={
                "uid": uid,
                "fromDate": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "toDate": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            }
        )
        response.raise_for_status()
        return response.json()

    def discover_endpoints(self) -> dict:
        """
        Try to discover available API endpoints.

        Returns:
            Dict mapping endpoints to their responses
        """
        self._ensure_logged_in()

        uid = self._devices[0] if self._devices else "test"

        # Comprehensive list of endpoint patterns to try
        endpoints = [
            # Service endpoints (from existing econet24-api library)
            "/service/getDevices",
            "/service/getUserDevices",
            "/service/getDeviceInfo",
            "/service/getDevice",
            "/service/getSysParams",
            "/service/getRegParams",
            "/service/getRegParamsData",
            "/service/getCurrentParams",
            "/service/getParams",
            "/service/getParamsValues",
            "/service/getStatus",
            "/service/getEditableParams",
            "/service/getAlarms",
            "/service/getErrors",
            "/service/getStatistics",
            "/service/getModes",
            # With UID parameter
            f"/service/getDeviceInfo?uid={uid}",
            f"/service/getSysParams?uid={uid}",
            f"/service/getRegParams?uid={uid}",
            f"/service/getRegParamsData?uid={uid}",
            f"/service/getCurrentParams?uid={uid}",
            f"/service/getParams?uid={uid}",
            f"/service/getStatus?uid={uid}",
            # View/device endpoints (based on redirect URL pattern)
            f"/view/device/{uid}/",
            f"/view/device/{uid}/main/",
            f"/view/device/{uid}/data/",
            f"/view/device/{uid}/params/",
            f"/view/device/{uid}/status/",
            f"/view/device/{uid}/api/",
            f"/view/device/{uid}/regParams/",
            f"/view/device/{uid}/sysParams/",
            # AJAX/API endpoints that pages might call
            f"/ajax/device/{uid}/params/",
            f"/ajax/device/{uid}/data/",
            f"/ajax/device/{uid}/status/",
            f"/api/device/{uid}/",
            f"/api/device/{uid}/params/",
            f"/api/device/{uid}/data/",
            # Common REST patterns
            f"/devices/{uid}/",
            f"/devices/{uid}/params/",
            f"/devices/{uid}/data/",
            # API endpoints (alternative pattern)
            "/api/devices",
            "/api/params",
            "/api/status",
            # Panel/dashboard endpoints
            "/panel/data",
            "/dashboard/data",
        ]

        results = {}
        for endpoint in endpoints:
            try:
                response = self._get(endpoint)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        results[endpoint] = {
                            "status": "success",
                            "data": data
                        }
                        logger.info(f"SUCCESS: {endpoint}")
                    except:
                        if len(response.text) < 1000:
                            results[endpoint] = {
                                "status": "html",
                                "preview": response.text[:200]
                            }
                elif response.status_code == 404:
                    pass  # Expected for non-existent endpoints
                else:
                    results[endpoint] = {
                        "status": response.status_code
                    }
            except Exception as e:
                logger.debug(f"Error testing {endpoint}: {e}")

        return results

    @property
    def devices(self) -> list:
        """Get cached list of device UIDs."""
        return self._devices


def main():
    """Test the client."""
    import os
    import json

    # Get credentials from environment or prompt
    username = os.environ.get("ECONET24_USERNAME")
    password = os.environ.get("ECONET24_PASSWORD")

    if not username or not password:
        print("Set ECONET24_USERNAME and ECONET24_PASSWORD environment variables")
        print("Or run interactively:")
        username = input("Email: ")
        password = input("Password: ")

    client = Econet24Client()

    try:
        print("\n=== Logging in ===")
        client.login(username, password)

        print(f"\n=== Devices ===")
        print(f"Found devices: {client.devices}")

        print("\n=== Getting Device Parameters ===")
        params = client.get_device_params()
        print(f"Keys in response: {list(params.keys())}")
        print(f"WiFi Quality: {params.get('wifiQuality')}%")
        print(f"WiFi Strength: {params.get('wifiStrength')} dBm")

        print("\n=== Current Sensor Values ===")
        current = params.get("curr", {})
        units = params.get("currUnits", {})

        # Print all current values with units
        for key in sorted(current.keys()):
            value = current[key]
            unit = units.get(key, "")
            # Skip values that are 999.0 (typically means "not connected")
            if value == 999.0:
                continue
            print(f"  {key}: {value} {unit}")

        print("\n=== Full curr data (JSON) ===")
        print(json.dumps(current, indent=2, default=str))

        print("\n=== Units mapping ===")
        print(json.dumps(units, indent=2, default=str))

    except LoginError as e:
        print(f"Login failed: {e}")
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
