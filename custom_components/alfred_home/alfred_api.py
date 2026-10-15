"""Asynchronous API Client for Alfred Smart Locks.

Reconstructed from com.alfred.home Android application (v1.9.25).
Supports NaCl Curve25519-XSalsa20-Poly1305 authentication, UAC1 HMAC-SHA256
request signing, real-time gateway telemetry, and transparent bridge commands.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import random
import time
from typing import Any
from urllib.parse import urlparse

import aiohttp
import nacl.public
import nacl.utils

from .const import (
    AGENT_NAME,
    AGENT_TOKEN,
    APP_VENDOR,
    APP_VERSION,
    HUB_SERVER,
    LOCK_SERVER,
    UAC_SERVER,
)

_LOGGER = logging.getLogger(__name__)


def _base64url(data: bytes) -> str:
    """Encode bytes to Base64URL without padding."""
    return base64.b64encode(data).decode("ascii").replace("+", "-").replace("/", "_").rstrip("=")


class AlfredAuthError(Exception):
    """Raised when authentication fails."""


class AlfredApiError(Exception):
    """Raised when an API error occurs."""


class AlfredDeviceTimeout(AlfredApiError):
    """Raised when bridge / lock communication times out."""


class AlfredApiClient:
    """API client for Alfred IoT cloud services."""

    def __init__(
        self,
        account: str,
        password: str | None = None,
        session: aiohttp.ClientSession | None = None,
        tokens: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the Alfred API client."""
        self.account = account.strip().lower()
        self.password = password
        self._session = session
        self._tokens = tokens or {}
        self._owns_session = False

    @property
    def is_authenticated(self) -> bool:
        """Return True if the client has active access tokens."""
        return bool(self._tokens.get("accessToken") and self._tokens.get("signToken"))

    @property
    def tokens(self) -> dict[str, Any]:
        """Return currently stored authentication tokens."""
        return self._tokens

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the underlying session if owned."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    def _wrap_payload(self, data: Any) -> dict[str, Any]:
        """Wrap payload in standard Alfred metadata envelope."""
        return {
            "meta": {
                "account": self.account,
                "devtype": "Android",
                "version": APP_VERSION,
                "locale": "en_US",
                "localtz": -144,
                "appVendorCode": APP_VENDOR,
                "x-agent-token": AGENT_TOKEN,
            },
            "data": data,
        }

    def _sign_request(self, url: str, body_bytes: bytes, sign_token: str) -> str:
        """Generate X-UAC-Signature header for authenticated requests."""
        path = urlparse(url).path
        if not path.startswith("/"):
            path = "/" + path

        body_sha256 = hashlib.sha256(body_bytes).hexdigest()
        canonical_req = f"POST\n{path}\n{body_sha256}\n"
        canonical_hash = hashlib.sha256(canonical_req.encode("utf-8")).hexdigest()

        timestamp = str(int(time.time() * 1000))
        string_to_sign = f"HMAC-SHA256\n{timestamp}\n{canonical_hash}"

        mac = hmac.new(
            sign_token.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        sig_b64 = _base64url(mac)
        return f"UAC1-HMAC-SHA256;{timestamp};{sig_b64}"

    async def _request(
        self,
        url: str,
        data: Any,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        """Execute POST request with compact JSON and UAC signature."""
        session = await self._get_session()
        payload = self._wrap_payload(data)
        body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body_bytes)),
            "User-Agent": f"AlfredHome/1.9.25 ({AGENT_NAME})",
        }

        if authenticated:
            if not self.is_authenticated:
                await self.login()

            access_token = self._tokens.get("accessToken")
            sign_token = self._tokens.get("signToken")

            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"

            if sign_token:
                headers["X-UAC-Signature"] = self._sign_request(url, body_bytes, sign_token)

        async with session.post(url, data=body_bytes, headers=headers) as response:
            try:
                res_data = await response.json()
            except Exception:
                text = await response.text()
                raise AlfredApiError(f"Invalid server response (HTTP {response.status}): {text}")

            err_code = res_data.get("code")
            if err_code in (401, 403) or (res_data.get("status") == "error" and err_code in (1100, 1101)):
                # Token might be expired or invalidated, re-authenticate if password is known
                if authenticated and self.password:
                    _LOGGER.info("Session expired or unauthorized (code %s), re-authenticating...", err_code)
                    await self.login()
                    return await self._request(url, data, authenticated=True)

            if res_data.get("status") == "error" and err_code not in (0, None):
                msg = res_data.get("message") or f"Error code {err_code}"
                raise AlfredApiError(f"Alfred API error on {url}: {msg} (code {err_code})")

            return res_data

    async def login(self) -> dict[str, Any]:
        """Authenticate using Curve25519 pre-auth challenge and NaCl Box."""
        if not self.password:
            raise AlfredAuthError("Password is required for login.")

        session = await self._get_session()

        # Step 1: Pre-auth Challenge
        challenge_req = self._wrap_payload({
            "username": self.account,
            "action": "signin",
            "agentName": AGENT_NAME,
            "agentToken": AGENT_TOKEN,
            "osName": "android",
        })
        chal_bytes = json.dumps(challenge_req, separators=(",", ":")).encode("utf-8")

        async with session.post(
            f"{UAC_SERVER}/v1/challenge",
            data=chal_bytes,
            headers={"Content-Type": "application/json"},
        ) as resp:
            chal_res = await resp.json()

        if chal_res.get("code") != 0 or not chal_res.get("result"):
            msg = chal_res.get("message") or "Challenge request failed"
            raise AlfredAuthError(f"Challenge failed: {msg}")

        server_pub_b64 = chal_res["result"]["serverPubKey"]
        client_sec_b64 = chal_res["result"]["clientSecretKey"]

        # Step 2: Encrypt password with NaCl Box
        try:
            server_pub = nacl.public.PublicKey(base64.b64decode(server_pub_b64))
            client_sec = nacl.public.PrivateKey(base64.b64decode(client_sec_b64))
            nonce = nacl.utils.random(24)
            box = nacl.public.Box(client_sec, server_pub)
            encrypted = box.encrypt(self.password.encode("utf-8"), nonce)

            ciphertext_b64 = base64.b64encode(encrypted.ciphertext).decode("ascii")
            nonce_b64 = base64.b64encode(nonce).decode("ascii")
        except Exception as err:
            raise AlfredAuthError(f"Failed to encrypt credentials: {err}") from err

        # Step 3: Sign In
        signin_req = self._wrap_payload({
            "username": self.account,
            "password": ciphertext_b64,
            "nonce": nonce_b64,
            "agentName": AGENT_NAME,
            "agentToken": AGENT_TOKEN,
            "osName": "android",
        })
        signin_bytes = json.dumps(signin_req, separators=(",", ":")).encode("utf-8")

        async with session.post(
            f"{UAC_SERVER}/v1/signin",
            data=signin_bytes,
            headers={"Content-Type": "application/json"},
        ) as resp:
            signin_res = await resp.json()

        if signin_res.get("code") != 0:
            msg = signin_res.get("message") or "Invalid credentials"
            raise AlfredAuthError(f"Authentication failed: {msg}")

        tokens = signin_res.get("result") or signin_res.get("data")
        if not tokens or not tokens.get("accessToken"):
            raise AlfredAuthError("No access tokens returned by server.")

        self._tokens = tokens
        _LOGGER.info("Successfully authenticated Alfred account: %s", self.account)
        return tokens

    async def get_devices(self) -> list[dict[str, Any]]:
        """Fetch registered door locks and Wi-Fi bridges."""
        res = await self._request(f"{UAC_SERVER}/v2/device-list", None)
        result = res.get("result") or {}
        con_devices = result.get("conDevices") or []
        dev_generals = result.get("devGenerals") or []

        # Map slave to master bridge
        master_map: dict[str, str] = {}
        for gen in dev_generals:
            slaves = gen.get("slaves") or []
            for slave_id in slaves:
                master_map[slave_id] = gen.get("deviceId", "")
            if gen.get("master"):
                master_map[gen["deviceId"]] = gen["master"]

        devices: list[dict[str, Any]] = []
        for dev in con_devices:
            dev_type = dev.get("deviceType")
            is_lock = dev_type in (2, 3)
            is_bridge = dev_type in (8, 1)

            device_id = dev.get("deviceId", "")
            master_id = master_map.get(device_id, "")

            devices.append({
                "deviceId": device_id,
                "name": dev.get("aliasName") or ("Front Door" if is_lock else "Wifi Bridge"),
                "mac": dev.get("mac", "Unknown"),
                "deviceType": dev_type,
                "isLock": is_lock,
                "isBridge": is_bridge,
                "masterId": master_id,
            })

        return devices

    async def get_device_status(self, bridge_id: str, lock_id: str) -> dict[str, Any]:
        """Query real-time hardware status and BLE telemetry."""
        req_data = {
            "devs": [
                {
                    "deviceId": bridge_id,
                    "deviceType": 8,
                    "subDevices": [
                        {
                            "deviceId": lock_id,
                            "deviceType": 2,
                        }
                    ],
                }
            ]
        }

        res = await self._request(f"{HUB_SERVER}/v2/devstatus", req_data)
        res_result = res.get("result") if isinstance(res.get("result"), dict) else {}
        values = res_result.get("value") or []

        bridge_val = next((v for v in values if v.get("deviceId") == bridge_id), values[0] if values else {})
        sub_devices = bridge_val.get("subDevices") or []
        lock_val = next((s for s in sub_devices if s.get("deviceId") == lock_id), {})

        # DoorLockStatus.java mapping:
        # raw lockStatus: 1 => UNLOCKED (app state 2)
        # raw lockStatus: 0 => LOCKED (app state 3)
        raw_lock_status = lock_val.get("lockStatus", 0)
        is_locked = raw_lock_status != 1

        # Fallback to True for bridge_online if bridge status not explicitly offline
        is_bridge_online = bridge_val.get("onlineStatus", 2) == 2
        is_lock_ble_connected = lock_val.get("onlineStatus", 2) == 2

        return {
            "bridge_online": is_bridge_online,
            "lock_online": is_lock_ble_connected,
            "is_locked": is_locked,
            "door_sensor_open": lock_val.get("doorsensor") == 1,
            "ble_signal": lock_val.get("blesignal"),
            "ble_signal_ts": lock_val.get("blesignalTs"),
            "malfunction": lock_val.get("malfunction", 0) != 0,
        }

    async def get_lock_detail(self, lock_id: str) -> dict[str, Any]:
        """Fetch lock detailed configuration and hardware state including battery level."""
        req_data = {
            "devs": [
                {
                    "deviceid": lock_id,
                    "isshare": 0,
                }
            ]
        }
        res = await self._request(f"{LOCK_SERVER}/v3/dev/detail", req_data)
        result = res.get("result") or []
        if isinstance(result, list) and len(result) > 0:
            lock_item = result[0]
            extend = lock_item.get("extend") or {}
            ability = lock_item.get("ability") or {}
            # extend.doorsensor is -1 when unsupported
            # ability may specify doorsensor capability if equipped
            doorsensor_supported = extend.get("doorsensor", -1) != -1 or bool(ability.get("doorsensor", {}).get("enable", 0))

            return {
                "mongodb_id": lock_item.get("_id"),
                "battery": extend.get("battery"),
                "battery_time": extend.get("batterytime"),
                "model": lock_item.get("mode") or "DB1",
                "fw_version": extend.get("fwversion") or extend.get("softversion"),
                "has_doorsensor": doorsensor_supported,
                "raw_extend": extend,
            }
        return {}

    async def get_lock_keypersons(self, mongo_did: str) -> list[dict[str, Any]]:
        """Fetch registered PIN user profiles (KeyPersons) for the lock."""
        try:
            res = await self._request(f"{LOCK_SERVER}/v1/dev/keyperson", {"did": mongo_did})
            result = res.get("result") or {}
            keypersons = result.get("keypersons") or []
            return keypersons
        except Exception as err:
            _LOGGER.debug("Could not fetch keypersons for did %s: %s", mongo_did, err)
            return []

    async def get_lock_activity_logs(self, mongo_did: str, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch recent lock event logs from the cloud."""
        try:
            res = await self._request(
                f"{LOCK_SERVER}/v1/dev/showlog",
                {"did": mongo_did, "limit": limit, "page": 1},
            )
            result = res.get("result") or {}
            logs = result.get("logs") or []
            return logs
        except Exception as err:
            _LOGGER.debug("Could not fetch activity logs for did %s: %s", mongo_did, err)
            return []

    async def operate_lock(self, lock_id: str, bridge_id: str, lock: bool) -> bool:
        """Lock or unlock the door through the Wi-Fi bridge."""
        # 1. Access Check (/v1/dev/access)
        access_payload = {
            "did": lock_id,
            "isshare": 0,
            "type": 2 if lock else 1,
        }
        await self._request(f"{LOCK_SERVER}/v1/dev/access", access_payload)

        # 2. Build 20-byte transparent binary frame
        param_bytes = bytearray(16)
        param_bytes[0] = 1 if lock else 0  # 1 = Close (Lock), 0 = Open (Unlock)
        param_bytes[1] = 4                # Operation code

        frame20 = bytearray(20)
        checksum = sum(param_bytes) & 0xFF
        frame20[2] = checksum
        frame20[3] = 0x02  # CMD_DOOR_CONTROL
        frame20[4:20] = param_bytes

        hex_frame = frame20.hex().upper()
        seq_id = random.randint(100000, 899999)

        # 3. Transmit transparent command to bridge
        cmd_payload = {
            "deviceId": bridge_id,
            "subDeviceId": lock_id,
            "ackFlag": True,
            "seqId": seq_id,
            "data": hex_frame,
        }
        cmd_res = await self._request(f"{HUB_SERVER}/v1/transparent-cmd", cmd_payload)
        if cmd_res.get("code") != 0:
            raise AlfredApiError(f"Bridge rejected command: {cmd_res.get('message')}")

        # 4. Poll execution result until physical confirmation
        poll_payload = {
            "deviceId": bridge_id,
            "subDeviceId": lock_id,
            "seqId": seq_id,
        }

        max_attempts = 12
        for _ in range(max_attempts):
            await asyncio.sleep(1.5)
            poll_res = await self._request(f"{HUB_SERVER}/v1/transparent-cmd-res", poll_payload)
            res_obj = poll_res.get("result") or {}
            status = str(res_obj.get("status", "0"))

            if status == "1":
                _LOGGER.info("Physical lock successfully executed command (lock=%s)", lock)
                return True
            if status == "2":
                err_code = res_obj.get("err", 0)
                err_messages = {
                    2: "Lock did not respond in time (REQUEST_TIMEOUT)",
                    3: "Bluetooth link dropped between Bridge and Lock (CONNECTION_DISCONNECTED)",
                    4: "Lock is in safe mode (REQUEST_BLOCK_SAFE_MODE)",
                    5: "Inside privacy switch engaged (REQUEST_BLOCK_INSIDE_LOCK)",
                }
                msg = err_messages.get(err_code, f"Error code {err_code}")
                raise AlfredApiError(f"Lock command failed: {msg}")

        raise AlfredDeviceTimeout(
            "Bridge timed out waiting for Bluetooth confirmation from lock. "
            "Please ensure the bridge is near the lock or tap the lock keypad to wake it."
        )
