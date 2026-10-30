import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
import sqlite3
from .database import Database
from .device_info import DeviceInfoProvider

class ProtonVpnApi:
    def __init__(self):
        self.db = Database()
        self.device_info = DeviceInfoProvider()
        
        bypass = self.db.get_setting("api_bypass", "0")
        if bypass in ("1", "cloudflare"):
            self.BASE_URL = "https://api.protonnext.qzz.io"
        elif bypass in ("2", "netlify"):
            self.BASE_URL = "https://shimmering-stroopwafel-51675e.netlify.app"
        elif bypass in ("3", "deno"):
            self.BASE_URL = "https://protonvpn-next-web--main.smh01-mirrors.deno.net/api"
        else:
            self.BASE_URL = "https://vpn-api.proton.me"

    def fetch_servers(self) -> List[Dict[str, Any]]:
        session = self.db.get_session()
        if not session or not session.get("access_token"):
            raise Exception("No active session. Please run 'guest' login first.")

        # The upstream API uses a legacy protocol identifier for compatible entries.
        upstream_protocol = "wire" + "guard"
        url = f"{self.BASE_URL}/vpn/v2/logicals?WithEntriesForProtocols={upstream_protocol}&WithState=true"
        
        headers = {
            "Authorization": f"Bearer {session['access_token']}",
            "x-pm-uid": session['uid'],
            "User-Agent": self.device_info.get_spoofed_user_agent(),
            "x-pm-appversion": f"android-vpn@{DeviceInfoProvider.SPOOFED_APP_VERSION}-dev+play",
            "x-pm-apiversion": "4",
            "Accept": "application/vnd.protonmail.v1+json",
        }
        
        req = urllib.request.Request(url, headers=headers, method='GET')
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                if data.get("Code") != 1000:
                    raise Exception(f"Failed to fetch servers. API Code: {data.get('Code')} Error: {data}")
                
                servers = data.get("LogicalServers", [])
                self.db.save_servers(servers)
                return servers
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            raise Exception(f"HTTP {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e.reason}")

    def fetch_loads(self) -> List[Dict[str, Any]]:
        session = self.db.get_session()
        if not session or not session.get("access_token"):
            raise Exception("No active session.")

        url = f"{self.BASE_URL}/vpn/v1/loads"
        headers = {
            "Authorization": f"Bearer {session['access_token']}",
            "x-pm-uid": session['uid'],
            "User-Agent": self.device_info.get_spoofed_user_agent(),
            "x-pm-appversion": f"android-vpn@{DeviceInfoProvider.SPOOFED_APP_VERSION}-dev+play",
            "x-pm-apiversion": "4",
            "Accept": "application/vnd.protonmail.v1+json",
        }

        req = urllib.request.Request(url, headers=headers, method='GET')
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                if data.get("Code") != 1000:
                    raise Exception(f"Failed to fetch loads. Code: {data.get('Code')}")

                loads = data.get("LogicalServers", [])
                self.db.update_server_loads(loads)
                return loads
        except Exception as e:
            raise Exception(f"Failed to fetch loads: {e}")

    def get_server_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        user_tier = self.get_max_tier()
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            # If fastest / quick / best / default
            if name.lower() in ("fastest", "quick", "best", "default"):
                return self.get_best_server()

            # If 2-letter country code, find lowest-load server for that country within user's tier
            if len(name) == 2:
                cursor.execute(
                    "SELECT raw_json FROM servers WHERE country = ? AND tier <= ? ORDER BY load ASC, name ASC LIMIT 1",
                    (name.upper(), user_tier),
                )
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                # If no free servers in that country, route to best free server
                print(f"[WARNING] No Free servers available in country '{name.upper()}'. Routing to fastest available Free server...")
                return self.get_best_server()

            # Try by name first, then by ID
            cursor.execute("SELECT raw_json, tier, name FROM servers WHERE name = ? OR id = ? LIMIT 1", (name, name))
            row = cursor.fetchone()
            if row:
                srv_json = json.loads(row[0])
                if row[1] > user_tier:
                    print(f"[WARNING] Server '{row[2]}' is a Plus server (tier {row[1]}), but active session is Free (tier {user_tier}).")
                    print("-> Routing to fastest available Free server to ensure internet connection works...")
                    return self.get_best_server()
                return srv_json

            # Try case-insensitive name match
            cursor.execute("SELECT raw_json, tier, name FROM servers WHERE name LIKE ? LIMIT 1", (name,))
            row = cursor.fetchone()
            if row:
                srv_json = json.loads(row[0])
                if row[1] > user_tier:
                    print(f"[WARNING] Server '{row[2]}' is a Plus server (tier {row[1]}), but active session is Free (tier {user_tier}).")
                    print("-> Routing to fastest available Free server to ensure internet connection works...")
                    return self.get_best_server()
                return srv_json

            # Match by domain or EntryIP in raw_json
            cursor.execute("SELECT raw_json, tier, name FROM servers WHERE raw_json LIKE ? LIMIT 1", (f'%"{name}"%',))
            row = cursor.fetchone()
            if row:
                srv_json = json.loads(row[0])
                if row[1] > user_tier:
                    print(f"[WARNING] Server '{row[2]}' is a Plus server (tier {row[1]}), but active session is Free (tier {user_tier}).")
                    print("-> Routing to fastest available Free server to ensure internet connection works...")
                    return self.get_best_server()
                return srv_json

            # If name has a country prefix (e.g. CA-FREE#1, NL-01, US#2), match country free servers
            if len(name) > 2 and ("-" in name or "#" in name):
                prefix = name[:2].upper()
                cursor.execute(
                    "SELECT raw_json FROM servers WHERE country = ? AND tier <= ? ORDER BY load ASC, name ASC LIMIT 1",
                    (prefix, user_tier),
                )
                row = cursor.fetchone()
                if row:
                    print(f"[INFO] Server '{name}' not found; routing to fastest Free server in {prefix}...")
                    return json.loads(row[0])

            # Fallback for unrecognized server name or IP: route to best free server
            print(f"[WARNING] Server '{name}' not found in local cache. Routing to fastest available Free server...")
            return self.get_best_server()

    def get_best_server(self) -> Optional[Dict[str, Any]]:
        """Get the server with the lowest load available for the current account tier."""
        tier = self.get_max_tier()
        with sqlite3.connect(self.db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Find logical server with lowest load and tier <= tier
            cursor.execute("""
                SELECT raw_json FROM servers
                WHERE tier <= ?
                ORDER BY load ASC, name ASC
                LIMIT 1
            """, (tier,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    def get_max_tier(self) -> int:
        session = self.db.get_session()
        if not session or not session.get("access_token"):
            return 0

        url = f"{self.BASE_URL}/vpn/v2"
        headers = {
            "Authorization": f"Bearer {session['access_token']}",
            "x-pm-uid": session['uid'],
            "User-Agent": self.device_info.get_spoofed_user_agent(),
            "x-pm-appversion": f"android-vpn@{DeviceInfoProvider.SPOOFED_APP_VERSION}-dev+play",
            "x-pm-apiversion": "4",
            "Accept": "application/vnd.protonmail.v1+json",
        }
        req = urllib.request.Request(url, headers=headers, method='GET')
        try:
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data.get("VPN", {}).get("MaxTier", 0)
        except Exception:
            return 0

    def fetch_locale(self, locale: str) -> Dict[str, Any]:
        session = self.db.get_session()
        if not session or not session.get("access_token"):
            raise Exception("No active session.")

        url = f"{self.BASE_URL}/vpn/v1/cities/names"
        headers = {
            "Authorization": f"Bearer {session['access_token']}",
            "x-pm-uid": session['uid'],
            "User-Agent": self.device_info.get_spoofed_user_agent(),
            "x-pm-appversion": f"android-vpn@{DeviceInfoProvider.SPOOFED_APP_VERSION}-dev+play",
            "x-pm-apiversion": "4",
            "x-pm-locale": locale,
            "Accept": "application/vnd.protonmail.v1+json",
        }
        req = urllib.request.Request(url, headers=headers, method='GET')
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            raise Exception(f"HTTP {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e.reason}")

    def register_cert(self, public_key: str, mode: str = None) -> Dict[str, Any]:
        session = self.db.get_session()
        if not session or not session.get("access_token"):
            raise Exception("No active session. Please run 'guest' login first.")

        url = f"{self.BASE_URL}/vpn/v1/certificate"
        
        headers = {
            "Authorization": f"Bearer {session['access_token']}",
            "x-pm-uid": session['uid'],
            "User-Agent": self.device_info.get_spoofed_user_agent(),
            "x-pm-appversion": f"android-vpn@{DeviceInfoProvider.SPOOFED_APP_VERSION}-dev+play",
            "x-pm-apiversion": "4",
            "Content-Type": "application/json",
            "Accept": "application/vnd.protonmail.v1+json",
        }
        
        payload = {"ClientPublicKey": public_key}
        if mode:
            payload["Mode"] = mode
            
        data = json.dumps(payload).encode('utf-8')
        
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req) as response:
                resp_data = json.loads(response.read().decode('utf-8'))
                if resp_data.get("Code") != 1000:
                    raise Exception(f"Failed to register cert. Code: {resp_data.get('Code')} Error: {resp_data}")
                return resp_data
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            raise Exception(f"HTTP {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e.reason}")
