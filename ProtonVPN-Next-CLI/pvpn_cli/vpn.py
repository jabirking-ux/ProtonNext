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

    def get_rotate_server(self, exclude_name: str = "") -> Optional[Dict[str, Any]]:
        """Select a free server in a DIFFERENT country than the currently active or excluded server."""
        import random, os
        tier = self.get_max_tier()
        
        current_server = exclude_name
        current_country = ""
        
        if not current_server:
            try:
                from .routing import get_config_dir
                routing_file = os.path.join(get_config_dir(), "routing_state.json")
                if os.path.exists(routing_file):
                    with open(routing_file, "r") as f:
                        st = json.load(f)
                        current_server = st.get("server_name", "")
            except Exception:
                pass
                
        if current_server and len(current_server) >= 2:
            current_country = current_server[:2].upper()
            
        with sqlite3.connect(self.db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT DISTINCT country FROM servers WHERE tier <= ?", (tier,))
            all_countries = [row[0] for row in cursor.fetchall()]
            
            other_countries = [c for c in all_countries if c.upper() != current_country]
            target_country = None
            if other_countries:
                target_country = random.choice(other_countries)
            elif all_countries:
                target_country = all_countries[0]
                
            if target_country:
                cursor.execute(
                    "SELECT raw_json FROM servers WHERE country = ? AND tier <= ? AND name != ? ORDER BY load ASC LIMIT 5",
                    (target_country, tier, current_server),
                )
                rows = cursor.fetchall()
                if rows:
                    return json.loads(random.choice(rows)[0])
                    
            return self.get_best_server(exclude_name=current_server, exclude_country=current_country)

    def get_server_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        import random
        user_tier = self.get_max_tier()
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            if name.lower().startswith("rotate") or name.lower() in ("change_server", "random_free"):
                exclude_server = ""
                if ":" in name:
                    exclude_server = name.split(":", 1)[1].strip()
                return self.get_rotate_server(exclude_name=exclude_server)

            if name.lower() in ("fastest", "quick", "best", "default"):
                return self.get_best_server()

            if len(name) == 2:
                cursor.execute(
                    "SELECT raw_json FROM servers WHERE country = ? AND tier <= ? ORDER BY load ASC LIMIT 5",
                    (name.upper(), user_tier),
                )
                rows = cursor.fetchall()
                if rows:
                    return json.loads(random.choice(rows)[0])
                print(f"[WARNING] No Free servers available in country '{name.upper()}'. Routing to fastest available Free server...")
                return self.get_best_server()

            cursor.execute("SELECT raw_json, tier, name FROM servers WHERE name = ? OR id = ? LIMIT 1", (name, name))
            row = cursor.fetchone()
            if row:
                srv_json = json.loads(row[0])
                if row[1] > user_tier:
                    print(f"[WARNING] Server '{row[2]}' is a Plus server (tier {row[1]}), but active session is Free (tier {user_tier}).")
                    print("-> Routing to fastest available Free server to ensure internet connection works...")
                    return self.get_best_server()
                return srv_json

            cursor.execute("SELECT raw_json, tier, name FROM servers WHERE name LIKE ? LIMIT 1", (name,))
            row = cursor.fetchone()
            if row:
                srv_json = json.loads(row[0])
                if row[1] > user_tier:
                    print(f"[WARNING] Server '{row[2]}' is a Plus server (tier {row[1]}), but active session is Free (tier {user_tier}).")
                    print("-> Routing to fastest available Free server to ensure internet connection works...")
                    return self.get_best_server()
                return srv_json

            cursor.execute("SELECT raw_json, tier, name FROM servers WHERE raw_json LIKE ? LIMIT 1", (f'%"{name}"%',))
            row = cursor.fetchone()
            if row:
                srv_json = json.loads(row[0])
                if row[1] > user_tier:
                    print(f"[WARNING] Server '{row[2]}' is a Plus server (tier {row[1]}), but active session is Free (tier {user_tier}).")
                    print("-> Routing to fastest available Free server to ensure internet connection works...")
                    return self.get_best_server()
                return srv_json

            if len(name) > 2 and ("-" in name or "#" in name):
                prefix = name[:2].upper()
                cursor.execute(
                    "SELECT raw_json FROM servers WHERE country = ? AND tier <= ? ORDER BY load ASC LIMIT 5",
                    (prefix, user_tier),
                )
                rows = cursor.fetchall()
                if rows:
                    print(f"[INFO] Server '{name}' not found; routing to free server in {prefix}...")
                    return json.loads(random.choice(rows)[0])

            print(f"[WARNING] Server '{name}' not found in local cache. Routing to fastest available Free server...")
            return self.get_best_server()

    def get_best_server(self, exclude_name: str = None, exclude_country: str = None) -> Optional[Dict[str, Any]]:
        """Get the server with the lowest load available for the current account tier, balancing countries."""
        import random, os
        tier = self.get_max_tier()
        
        if not exclude_country:
            try:
                from .routing import get_config_dir
                routing_file = os.path.join(get_config_dir(), "routing_state.json")
                if os.path.exists(routing_file):
                    with open(routing_file, "r") as f:
                        st = json.load(f)
                        curr = st.get("server_name", "")
                        if curr and len(curr) >= 2:
                            exclude_country = curr[:2].upper()
            except Exception:
                pass

        with sqlite3.connect(self.db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT raw_json, country, name, load FROM servers
                WHERE tier <= ?
                ORDER BY load ASC
                LIMIT 40
            """, (tier,))
            rows = cursor.fetchall()
            if not rows:
                return None
                
            pool = [r for r in rows if r["country"] != exclude_country and (not exclude_name or r["name"] != exclude_name)]
            if not pool:
                pool = rows
                
            by_country = {}
            for r in pool:
                c = r["country"]
                if c not in by_country:
                    by_country[c] = []
                by_country[c].append(r)
                
            best_per_country = [server_list[0] for server_list in by_country.values()]
            best_per_country.sort(key=lambda x: x["load"])
            
            selection_pool = best_per_country[:min(3, len(best_per_country))]
            selected = random.choice(selection_pool)
            return json.loads(selected["raw_json"])

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
