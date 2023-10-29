import httpx
from datetime import datetime
import logging
from threading import Lock

_LOGGER = logging.getLogger(__name__)
_TOKEN_LOCK = Lock()


class ComapClient(object):
    _BASEURL = "https://api.comapsmarthome.com/"
    login_headers = {}
    login_payload = {}
    token = ""
    last_request = ""
    token_expires = ""
    clientid = ""

    def __init__(self, username, password, clientid="56jcvrtejpracljtirq7qnob44"):
        self.clientid = clientid
        self.login_headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "x-amz-target": "AWSCognitoIdentityProviderService.InitiateAuth",
            "origin": "https://app.comapsmarthome.com",
            "referer": "https://app.comapsmarthome.com",
        }
        self.login_payload = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "AuthParameters": {
                "USERNAME": username,
                "PASSWORD": password,
            },
            "ClientId": clientid,
        }
        try:
            self.login()
            housings = self.get_housings()
            self.housing = housings[0].get("id")
        except AttributeError as err:
            raise ComapClientAuthException from err

    def login(self):
        try:
            url = "https://cognito-idp.eu-west-3.amazonaws.com"
            login_request = httpx.post(
                url, json=self.login_payload, headers=self.login_headers
            )
            login_request.raise_for_status()
            response = login_request.json()
            self.last_request = datetime.now()
            self.token = response.get("AuthenticationResult").get("AccessToken")
            self.refresh_token = response.get("AuthenticationResult").get(
                "RefreshToken"
            )
            self.token_expires = response.get("AuthenticationResult").get("ExpiresIn")

        except httpx.HTTPStatusError as err:
            _LOGGER.error(
                "Could not set up COMAP client - %s status code. Check your credentials",
                err.response.status_code,
            )
            raise ComapClientAuthException(
                "Client set up failed", err.response.status_code
            ) from err

    def get_request(self, url, headers=None, params={}):
        if (datetime.now() - self.last_request).total_seconds() > (
            self.token_expires - 60
        ):
            self.token_refresh()
        if headers is None:
            headers = {
                "Authorization": "Bearer {}".format(self.token),
                "Content-Type": "application/json",
            }
        r = httpx.get(url=url, headers=headers, params=params)
        r.raise_for_status()
        return r.json()

    async def async_request(self, mode, url, headers=None, params={}, json={}):
        if (datetime.now() - self.last_request).total_seconds() > (
            self.token_expires - 60
        ):
            _LOGGER.debug("Attempting refresh of access token")
            self.token_refresh()
        if headers is None:
            headers = {
                "Authorization": "Bearer {}".format(self.token),
                "Content-Type": "application/json",
            }
        async with httpx.AsyncClient() as client:
            if mode == "post":
                r = await client.post(url=url, headers=headers, json=json)
            if mode == "put":
                r = await client.put(url=url, headers=headers, json=json)
            elif mode == "delete":
                r = await client.delete(url=url, headers=headers)
            elif mode == "get":
                r = await client.get(url=url, headers=headers, params=params)
            r.raise_for_status()
            return r.json()

    async def async_post(self, url, headers=None, json={}):
        return await self.async_request("post", url, headers, json=json)

    async def async_get(self, url, headers=None, params={}):
        return await self.async_request("get", url, headers, params=params)

    async def async_delete(self, url, headers=None):
        return await self.async_request("delete", url, headers)

    async def async_put(self, url, headers=None, json={}):
        return await self.async_request("put", url, headers, json=json)

    def token_refresh(self):
        url = "https://cognito-idp.eu-west-3.amazonaws.com"

        with _TOKEN_LOCK:
            headers = {
                "Content-Type": "application/x-amz-json-1.1",
                "x-amz-target": "AWSCognitoIdentityProviderService.InitiateAuth",
                "origin": "https://app.comapsmarthome.com",
                "referer": "https://app.comapsmarthome.com",
            }
            payload = {
                "AuthFlow": "REFRESH_TOKEN_AUTH",
                "AuthParameters": {"REFRESH_TOKEN": self.refresh_token},
                "ClientId": self.clientid,
            }

            login_request = httpx.post(url, json=payload, headers=headers)
            if login_request.status_code == 200:
                response = login_request.json()
                self.last_request = datetime.now()
                self.token = response.get("AuthenticationResult").get("AccessToken")
                self.token_expires = response.get("AuthenticationResult").get(
                    "ExpiresIn"
                )
            else:
                _LOGGER.error("Refresh token failed")

    def get_housings(self):
        return self.get_request(self._BASEURL + "park/housings")

    async def get_zones(self, housing=None):
        if housing is None:
            housing = self.housing
        return await self.async_get(
            self._BASEURL + "thermal/housings/" + housing + "/thermal-details"
        )

    def get_zone(self, zoneid, housing=None):
        if housing is None:
            housing = self.housing
        return self.get_request(
            self._BASEURL
            + "thermal/housings/"
            + housing
            + "/thermal-details/zones/"
            + zoneid
        )

    async def leave_home(self, housing=None):
        if housing is None:
            housing = self.housing
        return await self.async_post(
            self._BASEURL
            + "thermal/housings/"
            + housing
            + "/thermal-control/leave-home"
        )

    async def return_home(self, housing=None):
        """THis is used to cancel a leave home signal"""
        if housing is None:
            housing = self.housing
        return await self.async_delete(
            self._BASEURL
            + "thermal/housings/"
            + housing
            + "/thermal-control/leave-home"
        )

    async def away_return(self, housing=None):
        """This is used to cancel a programmed away mode."""
        if housing is None:
            housing = self.housing
        return await self.async_post(
            self._BASEURL
            + "thermal/housings/"
            + housing
            + "/thermal-control/come-back-home"
        )

    async def get_schedules(self, housing=None):
        """This returns a list of schedules available for a housing."""
        if housing is None:
            housing = self.housing
        return await self.async_get(
            self._BASEURL + "thermal/housings/" + housing + "/schedules"
        )

    async def get_custom_temperatures(self, housing=None):
        """This returns the temperatures corresponding to instructions for different zones."""
        if housing is None:
            housing = self.housing
        return await self.async_get(
            self._BASEURL + "thermal/housings/" + housing + "/custom-temperatures"
        )

    async def get_programs(self, housing=None):
        """This returns the active program and list of schedules for a housing."""
        if housing is None:
            housing = self.housing
        return await self.async_get(
            self._BASEURL + "thermal/housings/" + housing + "/programs"
        )

    async def get_active_schedules(self, housing=None):
        """Returns an array of zones with their active schedules"""
        programs = await self.get_programs(housing)
        active_schedules = []
        try:
            for program in programs["programs"]:
                if program["is_activated"]:
                    active_schedules = program["zones"]
        except AttributeError:
            _LOGGER.error("Could not find active program for Comap housing")

        return active_schedules

    async def set_schedule(
        self, zone, schedule_id, program_id=None, program_mode="connected", housing=None
    ):
        if housing is None:
            housing = self.housing
        if program_id is None:
            # get the current active program
            programs = await self.get_programs(housing)
            for program in programs["programs"]:
                if program["is_activated"] is True:
                    program_id = program["id"]
                    break
        data = {"schedule_id": schedule_id, "programming_type": program_mode}
        return await self.async_post(
            self._BASEURL
            + "thermal/housings/"
            + housing
            + "/programs/"
            + program_id
            + "/zones/"
            + zone,
            json=data,
        )

    async def set_temporary_instruction(
        self, zone, instruction, duration=120, housing=None
    ):
        """Set a temporary instruction for a zone, for a given duration in minutes"""
        if housing is None:
            housing = self.housing
        data = {"duration": duration, "set_point": {"instruction": instruction}}

        try:
            r = await self.async_post(
                self._BASEURL
                + "thermal/housings/"
                + housing
                + "/thermal-control/zones/"
                + zone
                + "/temporary-instruction",
                json=data,
            )
            return r
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 409:
                await self.remove_temporary_instruction(zone, housing)
                return await self.set_temporary_instruction(
                    zone, instruction, duration=duration, housing=housing
                )
            else:
                raise err

    async def remove_temporary_instruction(self, zone, housing=None):
        """Set a temporary instruction for a zone, for a given duration in minutes"""
        if housing is None:
            housing = self.housing

        try:
            r = await self.async_delete(
                self._BASEURL
                + "thermal/housings/"
                + housing
                + "/thermal-control/zones/"
                + zone
                + "/temporary-instruction",
            )
            return r
        except httpx.HTTPStatusError as err:
            _LOGGER.error(err)

    async def turn_on(self, housing=None):
        data = {"state": "on"}
        if housing is None:
            housing = self.housing
        return await self.async_put(
            self._BASEURL
            + "thermal/housings/"
            + housing
            + "/thermal-control/heating-system-state",
            json=data,
        )

    async def turn_off(self, housing=None):
        data = {"state": "off"}
        if housing is None:
            housing = self.housing
        return await self.async_put(
            self._BASEURL
            + "thermal/housings/"
            + housing
            + "/thermal-control/heating-system-state",
            json=data,
        )


class ComapClientException(Exception):
    """Exception with ComapSmartHome client."""


class ComapClientAuthException(Exception):
    """Exception with ComapSmartHome client."""
