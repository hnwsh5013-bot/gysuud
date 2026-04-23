import requests
import json
import time
import os
import re
import random
import binascii
import uuid
import secrets
import datetime
from datetime import timedelta
import threading
import queue
import urllib.parse
import string
import sys
from MedoSigner import Argus, Gorgon, md5, Ladon
import ms4
import SignerPy
import telebot
from flask import Flask, jsonify, request
import logging

# إعداد نظام التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# إنشاء تطبيق Flask
flask_app = Flask(__name__)

# ========== إعدادات Flask API ==========
flask_status = {
    "running": True,
    "start_time": time.time(),
    "requests_count": 0,
    "bot_users": 0
}

@flask_app.route('/', methods=['GET'])
def flask_home():
    flask_status["requests_count"] += 1
    return jsonify({
        "status": "active",
        "message": "Telegram Bot is running",
        "uptime": f"{int(time.time() - flask_status['start_time'])} seconds",
        "bot_users": flask_status["bot_users"]
    })

@flask_app.route('/status', methods=['GET'])
def flask_status_endpoint():
    return jsonify(flask_status)

@flask_app.route('/ping', methods=['GET'])
def flask_ping():
    return jsonify({"pong": True, "bot_alive": True})

# ========== إعدادات البوت الأصلي ==========
BOT_TOKEN = "8768112194:AAEBTVu8IO55Ntag5EkJowquaaGobyKQvCk"
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=100)

ADMIN_ID = 7055113715
FORCE_CHANNELS = ["@zzgkkk", "@WP_RD"]

FILES = {
    "users": "users.json",
    "banned": "banned.json",
    "notified": "notified.json",
    "stats": "stats.json"
}

def load(name):
    path = FILES[name]
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump([], f)
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        else:
            return []
    except:
        return []

def save(name, data):
    with open(FILES[name], "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_stats():
    path = FILES["stats"]
    if not os.path.exists(path):
        stats = {
            "total_users": 0,
            "private_users": 0,
            "channels_groups": 0,
            "banned_users": 0,
            "daily": {},
            "monthly": {},
            "started_users": {}
        }
        with open(path, "w") as f:
            json.dump(stats, f, indent=2)
        return stats
    try:
        with open(path, "r") as f:
            stats = json.load(f)
        if "daily" not in stats:
            stats["daily"] = {}
        if "monthly" not in stats:
            stats["monthly"] = {}
        if "started_users" not in stats:
            stats["started_users"] = {}
        return stats
    except:
        stats = {
            "total_users": 0,
            "private_users": 0,
            "channels_groups": 0,
            "banned_users": 0,
            "daily": {},
            "monthly": {},
            "started_users": {}
        }
        return stats

def save_stats(stats):
    with open(FILES["stats"], "w") as f:
        json.dump(stats, f, indent=2)

def update_stats(user_id, action="start"):
    stats = load_stats()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    month = datetime.datetime.now().strftime("%Y-%m")
    
    if today not in stats["daily"]:
        stats["daily"][today] = {"users": 0, "starts": 0, "messages": 0}
    if month not in stats["monthly"]:
        stats["monthly"][month] = {"new_users": 0}
    
    if action == "start":
        stats["daily"][today]["starts"] = stats["daily"][today].get("starts", 0) + 1
        if str(user_id) not in stats.get("started_users", {}):
            if "started_users" not in stats:
                stats["started_users"] = {}
            stats["started_users"][str(user_id)] = today
            stats["monthly"][month]["new_users"] = stats["monthly"][month].get("new_users", 0) + 1
            stats["daily"][today]["users"] = stats["daily"][today].get("users", 0) + 1
    elif action == "message":
        stats["daily"][today]["messages"] = stats["daily"][today].get("messages", 0) + 1
    
    save_stats(stats)
    users_list = load("users")
    flask_status["bot_users"] = len(users_list)

def send(chat_id, text, markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if markup:
        payload["reply_markup"] = json.dumps(markup)
    requests.post(API + "/sendMessage", data=payload)

def send_message(chat_id, text):
    requests.post(API + "/sendMessage", data={"chat_id": chat_id, "text": text})

def is_subscribed(uid):
    for ch in FORCE_CHANNELS:
        try:
            r = requests.get(API + "/getChatMember", params={
                "chat_id": ch,
                "user_id": uid
            }).json()
            if r.get("result", {}).get("status") not in ("member", "administrator", "creator"):
                return False
        except:
            return False
    return True

def mk(buttons):
    import json as _json
    return _json.dumps({"inline_keyboard": buttons}, ensure_ascii=False)

def T(cid, ar_text, en_text):
    lang = user_lang.get(cid, "ar")
    return en_text if lang == "en" else ar_text

def lang_markup():
    return mk([[
        {"text": "العربية ", "callback_data": "set_lang_ar", "style": "danger"},
        {"text": "English ", "callback_data": "set_lang_en", "style": "primary"},
    ]])

def force_markup_lang(cid):
    btns = []
    for i, ch in enumerate(FORCE_CHANNELS):
        if i == 0:
            label = T(cid, "القناة الأولى", "Channel 1")
        elif i == 1:
            label = T(cid, "القناة الثانية", "Channel 2")
        elif i == 2:
            label = T(cid, "القناة الثالثة", "Channel 3")
        elif i == 3:
            label = T(cid, "القناة الرابعة", "Channel 4")
        else:
            label = T(cid, f"القناة {i+1}", f"Channel {i+1}")
        btns.append([{"text": label, "url": f"https://t.me/{ch[1:]}", "style": "primary"}])
    btns.append([{"text": T(cid, "تحقق ✅", "Check ✅"), "callback_data": "check", "style": "success"}])
    return mk(btns)

def back_markup(cid):
    return mk([[
        {"text": T(cid, "↩️ رجوع", "↩️ Back"), "callback_data": "go_back", "style": "primary"}
    ]])

def main_markup_new(cid):
    return mk([
        [
            {"text": T(cid, "اخفاء الفيديوهات", "Hide Videos"), "callback_data": "hide_videos", "style": "success"},
            {"text": T(cid, "حذف المفضلات", "Delete Favorites"), "callback_data": "delete_favorites", "style": "success"},
        ],
        [
            {"text": T(cid, "حذف الريبوست", "Delete Reposts"), "callback_data": "delete_reposts", "style": "success"},
        ],
        [
            {"text": T(cid, "الغاء المتابعهم", "Unfollow All"), "callback_data": "unfollow_all", "style": "primary"},
            {"text": T(cid, "كشف ربوطات الحساب", "Check Bindings"), "callback_data": "check_bindings", "style": "primary"},
        ],
        [
            {"text": T(cid, "معلومات حساب من يوزر", "Info by Username"), "callback_data": "username", "style": "primary"},
            {"text": T(cid, "معلومات حساب من سيشن", "Info by Session"), "callback_data": "session", "style": "primary"},
        ],
        [
            {"text": T(cid, "فحص المحفظة", "Check Wallet"), "callback_data": "wallet", "style": "primary"},
        ],
        [
            {"text": T(cid, "سحب سيشن 🔗", "Pull Session 🔗"), "url": "https://vm.tiktok.com/ZSky7XAvV/", "style": "danger"},
        ],
        [
            {"text": T(cid, "تغيير اللغة", "Change Language"), "callback_data": "change_lang", "style": "primary"},
        ],
        [
            {"text": T(cid, "قناة المبرمج", "Dev Channel"), "url": "https://t.me/WP_RD", "style": "primary"},
            {"text": T(cid, "المبرمج", "Developer"), "url": "https://t.me/M_321", "style": "primary"},
        ],
    ])

def admin_markup_new():
    return mk([
        [{"text": "احصائيات البوت", "callback_data": "admin_stats", "style": "primary"}],
        [{"text": "اذاعة للمستخدمين", "callback_data": "admin_broadcast_users", "style": "success"}],
        [{"text": "اذاعة للقنوات", "callback_data": "admin_broadcast_channels", "style": "primary"}],
        [{"text": "اذاعة للمجموعات", "callback_data": "admin_broadcast_groups", "style": "primary"}],
        [{"text": "حظر مستخدم", "callback_data": "admin_ban", "style": "danger"}],
        [{"text": "فك حظر مستخدم", "callback_data": "admin_unban", "style": "success"}],
        [{"text": "عرض المحظورين", "callback_data": "admin_banned_list", "style": "primary"}],
    ])

def sign(params, payload=None, sec_device_id="", cookie=None,
         aid=1233, license_id=1611921764,
         sdk_version_str="2.3.1.i18n", sdk_version=2,
         platform=19, unix=None):
    x_ss_stub = md5(payload.encode()).hexdigest() if payload else None
    unix = unix or int(time.time())
    return Gorgon(params, unix, payload, cookie).get_value() | {
        "x-ladon": Ladon.encrypt(unix, license_id, aid),
        "x-argus": Argus.get_sign(
            params, x_ss_stub, unix,
            platform=platform,
            aid=aid,
            license_id=license_id,
            sec_device_id=sec_device_id,
            sdk_version=sdk_version_str,
            sdk_version_int=sdk_version
        )
    }

def lev(uid):
    try:
        url = f"https://webcast16-normal-no1a.tiktokv.eu/webcast/user/?target_uid={uid}&aid=1233"
        h = {"User-Agent": "com.zhiliaoapp.musically/2023001020"}
        h.update(sign(url.split("?")[1], "", "AadC" + secrets.token_hex(8)))
        r = requests.get(url, headers=h).text
        match = re.search(r'"default_pattern":"(.*?)"', r)
        if match:
            return match.group(1)
        return "غير متاح"
    except:
        return "غير متاح"

def info_session(sessionid):
    try:
        r = requests.get(
            "https://api16-normal-c-useast1a.tiktokv.com/passport/account/info/v2/",
            cookies={"sessionid": sessionid}
        )
        if r.status_code != 200:
            return None
        d = r.json()["data"]
        return {
            "username": d.get("username", ""),
            "email": d.get("email", ""),
            "mobile": d.get("mobile", ""),
            "session_key": d.get("session_key", ""),
            "user_verified": "Yes" if d.get("user_verified") else "No",
            "has_password": "Yes" if d.get("has_password") else "No",
            "sec_user_id": d.get("sec_user_id", "")
        }
    except:
        return None

def gets_mony(s):
    try:
        r = requests.get(
            "https://webcast.tiktok.com/webcast/wallet_api/diamond_buy/permission/?aid=1988",
            headers={"Cookie": f"sessionid={s}", "User-Agent": "Mozilla/5.0"}
        ).json()["data"]
        return r.get("coins", 0), r.get("exchange", {}).get("revenue", 0) / 100
    except:
        return 0, 0

def info_by_username(u):
    try:
        r = requests.get(f"https://www.tiktok.com/@{u}", headers={"User-Agent": "Mozilla/5.0"}).text
        g = r.split('webapp.user-detail"')[1].split('"RecommendUserList"')[0]
        
        def get_value(k, end='",'):
            try:
                return g.split(f'{k}":"')[1].split(end)[0]
            except:
                return ""
        
        uid = get_value("id")
        created = ""
        if uid:
            try:
                created = datetime.datetime.fromtimestamp(int("{0:b}".format(int(uid))[:31], 2)).year
            except:
                created = ""
        
        return {
            "id": uid,
            "name": get_value("nickname"),
            "followers": get_value("followerCount"),
            "following": get_value("followingCount"),
            "likes": get_value("heart"),
            "video": get_value("videoCount"),
            "country": get_value("region"),
            "bio": get_value("signature"),
            "private": get_value("privateAccount"),
            "created": created
        }
    except:
        return None

Hostnames = ["api16-normal-c-alisg.tiktokv.com", "api.tiktokv.com", "api-h2.tiktokv.com", "api-va.tiktokv.com", "api16.tiktokv.com", "api16-va.tiktokv.com", "api19.tiktokv.com", "api19-va.tiktokv.com", "api21.tiktokv.com", "api15-h2.tiktokv.com", "api21-h2.tiktokv.com", "api21-va.tiktokv.com", "api22.tiktokv.com", "api22-va.tiktokv.com", "api-t.tiktok.com", "api16-normal-baseline.tiktokv.com", "api23-normal-zr.tiktokv.com", "api21-normal.tiktokv.com", "api22-normal-zr.tiktokv.com", "api33-normal.tiktokv.com", "api22-normal.tiktokv.com", "api31-normal.tiktokv.com", "api15-normal.tiktokv.com", "api31-normal-cost-sg.tiktokv.com", "api3-normal.tiktokv.com", "api31-normal-zr.tiktokv.com", "api9-normal.tiktokv.com", "api16-normal.tiktokv.com", "api16-normal.ttapis.com", "api19-normal-zr.tiktokv.com", "api16-normal-zr.tiktokv.com", "api16-normal-apix.tiktokv.com", "api74-normal.tiktokv.com", "api32-normal-zr.tiktokv.com", "api23-normal.tiktokv.com", "api32-normal.tiktokv.com", "api16-normal-quic.tiktokv.com", "api-normal.tiktokv.com", "api16-normal-apix-quic.tiktokv.com", "api19-normal.tiktokv.com", "api31-normal-cost-mys.tiktokv.com", "im-va.tiktokv.com", "imapi-16.tiktokv.com", "imapi-16.musical.ly", "imapi-mu.isnssdk.com", "api.tiktok.com", "api.ttapis.com", "api.tiktokv.us", "api.tiktokv.eu", "api.tiktokw.us", "api.tiktokw.eu", "webcast-ws16-normal-useast5.tiktokv.us", "webcast-ws16-normal-useast8.tiktokv.us", "webcast16-normal-useast5.tiktokv.us", "webcast16-normal-useast8.tiktokv.us", "webcast19-normal-useast5.tiktokv.us", "webcast19-normal-useast8.tiktokv.us", "api.tiktokv.us", "api16-core-useast5.tiktokv.us", "api16-core-useast8.tiktokv.us", "api16-normal-useast5.tiktokv.us", "api16-normal-useast8.tiktokv.us", "api19-core-useast5.tiktokv.us", "api19-core-useast8.tiktokv.us", "api19-normal-useast5.tiktokv.us", "api19-normal-useast8.tiktokv.us", "ad.tiktokv.us", "tiktokv.us", "tiktokw.us"]

def get_available_ways(host, token, params, cookies):
    try:
        params_step2 = params.copy()
        params_step2['not_login_ticket'] = token
        params_step2['ts'] = str(int(time.time()))
        params_step2['_rticket'] = str(int(time.time() * 1000))
        url_step2 = f"https://{host}/passport/auth/available_ways/?" + urllib.parse.urlencode(params_step2)
        signature_step2 = SignerPy.sign(params=url_step2, payload=None, version=4404)
        
        headers_step2 = {
            'User-Agent': "com.zhiliaoapp.musically.go/410203 (Linux; U; Android 14; ar; RMX3834; Build/UP1A.231005.007;tt-ok/3.12.13.44.lite-ul)",
            'x-ss-req-ticket': signature_step2['x-ss-req-ticket'],
            'x-ss-stub': signature_step2['x-ss-stub'],
            'x-gorgon': signature_step2["x-gorgon"],
            'x-khronos': signature_step2["x-khronos"],
            'x-tt-passport-csrf-token': cookies['passport_csrf_token'],
            'passport_csrf_token': cookies['passport_csrf_token'],
            'content-type': "application/x-www-form-urlencoded",
            'x-ss-dp': "1340",
            'sdk-version': "2",
            'x-tt-ultra-lite': "1",
        }
        res_step2 = requests.post(url_step2, headers=headers_step2, cookies=cookies, timeout=15)
        response_json_step2 = res_step2.json()
        
        if 'success' in response_json_step2.get("message", ""):
            data_step2 = response_json_step2.get('data', {})
            return {
                'data': {
                    'has_email': data_step2.get('has_email', False),
                    'has_mobile': data_step2.get('has_mobile', False),
                    'has_oauth': data_step2.get('has_oauth', False),
                    'has_passkey': data_step2.get('has_passkey', False),
                    'oauth_platforms': data_step2.get('oauth_platforms', [])
                },
                'message': 'success',
                'host': host
            }
    except:
        pass
    return None

# ========== الدالة الجديدة المضافة ==========
def find_account_end_point_simple(username):
    """نسخة مبسطة لا تعتمد على SignerPy"""
    try:
        url = f"https://www.tikwm.com/api/user?unique_id={username}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('data'):
                user_data = data['data']
                platforms = []
                if user_data.get('ins_id'):
                    platforms.append("instagram")
                if user_data.get('youtube_channel_id'):
                    platforms.append("youtube")
                if user_data.get('bioLink', {}).get('link'):
                    platforms.append("website")
                return {
                    'data': {
                        'has_email': True,
                        'has_mobile': False,
                        'has_oauth': len(platforms) > 0,
                        'has_passkey': False,
                        'oauth_platforms': platforms
                    },
                    'message': 'success',
                    'host': 'tikwm'
                }
    except:
        pass
    return {
        'data': {
            'has_email': True,
            'has_mobile': False,
            'has_oauth': False,
            'has_passkey': False,
            'oauth_platforms': []
        },
        'message': 'success',
        'host': 'fallback'
    }

def find_account_end_point(username):
    for host in Hostnames:
        try:
            secret = secrets.token_hex(16)
            cookies = {
                "passport_csrf_token": secret,
                "passport_csrf_token_default": secret
            }
            params = {
                'request_tag_from': "h5",
                'manifest_version_code': "410203",
                '_rticket': str(int(time.time() * 1000)),
                'app_language': "ar",
                'app_type': "normal",
                'iid': str(random.randint(1, 10**19)),
                'app_package': "com.zhiliaoapp.musically.go",
                'channel': "googleplay",
                'device_type': "RMX3834",
                'language': "ar",
                'host_abi': "arm64-v8a",
                'locale': "ar",
                'resolution': "720*1454",
                'openudid': "b57299cf6a5bb211",
                'update_version_code': "410203",
                'ac2': "lte",
                'cdid': str(uuid.uuid4()),
                'sys_region': "EG",
                'os_api': "34",
                'timezone_name': "Asia/Baghdad",
                'dpi': "272",
                'carrier_region': "IQ",
                'ac': "4g",
                'device_id': str(random.randint(1, 10**19)),
                'os': "android",
                'os_version': "14",
                'timezone_offset': "10800",
                'version_code': "410203",
                'app_name': "musically_go",
                'ab_version': "41.2.3",
                'version_name': "41.2.3",
                'device_brand': "realme",
                'op_region': "IQ",
                'ssmix': "a",
                'device_platform': "android",
                'build_number': "41.2.3",
                'region': "EG",
                'aid': "1340",
                'ts': str(int(time.time())),
                'okhttp_version': "4.1.103.107-ul",
                'use_store_region_cookie': "1"
            }
            url = f"https://{host}/passport/find_account/tiktok_username/?" + urllib.parse.urlencode(params)
            payload = {'mix_mode': "1", 'username': username}
            signature = SignerPy.sign(params=url, payload=payload, version=4404)
            headers = {
                'User-Agent': "com.zhiliaoapp.musically.go/410203 (Linux; U; Android 14; ar; RMX3834; Build/UP1A.231005.007;tt-ok/3.12.13.44.lite-ul)",
                'x-ss-req-ticket': signature['x-ss-req-ticket'],
                'x-ss-stub': signature['x-ss-stub'],
                'x-gorgon': signature["x-gorgon"],
                'x-khronos': signature["x-khronos"],
                'x-tt-passport-csrf-token': cookies['passport_csrf_token'],
                'passport_csrf_token': cookies['passport_csrf_token'],
                'content-type': "application/x-www-form-urlencoded",
                'x-ss-dp': "1340",
                'sdk-version': "2",
                'x-tt-ultra-lite': "1",
                'x-vc-bdturing-sdk-version': "2.3.15.i18n",
                'ttzip-tlb': "1",
            }
            response = requests.post(url, data=payload, headers=headers, cookies=cookies, timeout=15)
            data = response.json()
            if data.get('message') == 'success':
                token = data["data"]["token"]
                return get_available_ways(host, token, params, cookies)
        except:
            pass
    return None

class karboxTool:
    def __init__(self, session_id):
        self.unfollowed = 0
        self.failed = 0
        self.total = 0
        self.stop_threads = False
        self.queue = queue.Queue()
        self.session_id = session_id
        
    def sig(self, prm, pl=None, aid=1340):
        t = int(time.time())
        ps = urllib.parse.urlencode(prm)
        if pl:
            pls = urllib.parse.urlencode(pl)
            xst = md5(pls.encode('utf-8')).hexdigest().upper()
        else:
            pls = ""
            xst = None
        gd = Gorgon(ps, t, pls, None).get_value()
        ln = Ladon.encrypt(t, 1611921764, aid)
        ag = Argus.get_sign(ps, xst, t, platform=19, aid=aid, license_id=1611921764, sec_device_id="", sdk_version="2.3.15.i18n", sdk_version_int=2)
        sigs = {
            "x-ladon": ln,
            "x-khronos": str(t),
            "x-argus": ag,
            "x-gorgon": gd.get("x-gorgon", ""),
            "x-ss-req-ticket": str(int(time.time() * 1000))
        }
        if xst:
            sigs["x-ss-stub"] = xst
        return sigs
    
    def kullanici_bilgisi_sessiondan(self):
        cookies = {'sessionid': self.session_id, 'sessionid_ss': self.session_id, 'sid_tt': self.session_id}
        headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        url = "https://www.tiktok.com/passport/web/account/info/"
        try:
            response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
            if response.status_code == 200:
                data = response.json().get("data", {})
                user_id = data.get("user_id_str", "")
                sec_user_id = data.get("sec_user_id", "")
                username = data.get("username", "")
                screen_name = data.get("screen_name", "")
                if user_id and sec_user_id:
                    return {'uid': user_id, 'sec': sec_user_id, 'name': screen_name, 'username': username}
            return None
        except:
            return None
    
    def sayfa_cek(self, uid, sec, tok=""):
        url = "https://api16-normal-c-alisg.tiktokv.com/lite/v2/relation/following/list/"
        prm = {
            'user_id': uid, 'count': "100", 'page_token': tok, 'source_type': "4",
            'request_tag_from': "h5", 'sec_user_id': sec, 'manifest_version_code': "400603",
            '_rticket': str(int(time.time() * 1000)), 'app_language': "tr", 'app_type': "normal",
            'iid': "7583278212717954823", 'app_package': "com.zhiliaoapp.musically.go",
            'channel': "googleplay", 'device_type': "RMX3834", 'language': "tr",
            'host_abi': "arm64-v8a", 'locale': "tr", 'resolution': "720*1454",
            'openudid': "b57299cf6a5bb211", 'update_version_code': "400603", 'ac2': "wifi",
            'cdid': "f7e5f9fe-bce4-48d5-8857-7caa1b0d34b8", 'sys_region': "TR",
            'os_api': "34", 'timezone_name': "Asia/Baghdad", 'dpi': "272",
            'carrier_region': "TR", 'ac': "wifi", 'device_id': "7456376313159714309",
            'os': "android", 'os_version': "14", 'timezone_offset': "10800",
            'version_code': "400603", 'app_name': "musically_go", 'ab_version': "40.6.3",
            'version_name': "40.6.3", 'device_brand': "realme", 'op_region': "TR",
            'ssmix': "a", 'device_platform': "android", 'build_number': "40.6.3",
            'region': "TR", 'aid': "1340", 'ts': str(int(time.time()))
        }
        s = self.sig(prm)
        hd = {'User-Agent': "com.zhiliaoapp.musically.go/400603 (Linux; U; Android 14; ar; RMX3834; Build/UP1A.231005.007;tt-ok/3.12.13.44.lite-ul)", 'Cookie': f"sessionid={self.session_id};"}
        if s:
            hd.update({'x-ladon': s.get("x-ladon", ""), 'x-khronos': s.get("x-khronos", ""), 'x-argus': s.get("x-argus", ""), 'x-gorgon': s.get("x-gorgon", ""), 'x-ss-req-ticket': s.get("x-ss-req-ticket", "")})
            if 'x-ss-stub' in s:
                hd['x-ss-stub'] = s['x-ss-stub']
        try:
            r = requests.get(url, params=prm, headers=hd, timeout=10)
            if r.status_code == 200:
                return r.json()
            else:
                return None
        except:
            return None
    
    def tum_takip_edilenleri_cek(self, uid, sec):
        tum_kullanicilar = []
        sayfa = 0
        daha_var = True
        token = ""
        maks_sayfa = 50
        while daha_var and sayfa < maks_sayfa:
            sayfa += 1
            d = self.sayfa_cek(uid, sec, token)
            if not d:
                break
            if d.get('status_code') != 0:
                break
            kullanicilar = d.get('followings', [])
            tum_kullanicilar.extend(kullanicilar)
            daha_var = d.get('has_more', False)
            token = d.get('next_page_token', "")
            if daha_var:
                time.sleep(0.3)
        return tum_kullanicilar
    
    def takipten_cik(self, target_id):
        url = "https://api16-normal-c-alisg.tiktokv.com/lite/v2/relation/follow/"
        prm = {
            'request_tag_from': "h5", 'manifest_version_code': "400603",
            '_rticket': str(int(time.time() * 1000)), 'app_language': "tr",
            'app_type': "normal", 'iid': "7583278212717954823",
            'app_package': "com.zhiliaoapp.musically.go", 'channel': "googleplay",
            'device_type': "RMX3834", 'language': "tr", 'host_abi': "arm64-v8a",
            'locale': "tr", 'resolution': "720*1454", 'openudid': "b57299cf6a5bb211",
            'update_version_code': "400603", 'ac2': "wifi",
            'cdid': "f7e5f9fe-bce4-48d5-8857-7caa1b0d34b8", 'sys_region': "TR",
            'os_api': "34", 'timezone_name': "Asia/Baghdad", 'dpi': "272",
            'carrier_region': "TR", 'ac': "wifi", 'device_id': "7456376313159714309",
            'os': "android", 'os_version': "14", 'timezone_offset': "10800",
            'version_code': "400603", 'app_name': "musically_go", 'ab_version': "40.6.3",
            'version_name': "40.6.3", 'device_brand': "realme", 'op_region': "TR",
            'ssmix': "a", 'device_platform': "android", 'build_number': "40.6.3",
            'region': "TR", 'aid': "1340", 'ts': str(int(time.time()))
        }
        pl = {'user_id': str(target_id), 'from_page': "following_list", 'from': "34", 'type': "0"}
        s = self.sig(prm, pl)
        hd = {
            'User-Agent': "com.zhiliaoapp.musically.go/400603 (Linux; U; Android 14; ar; RMX3834; Build/UP1A.231005.007;tt-ok/3.12.13.44.lite-ul)",
            'Cookie': f"sessionid={self.session_id};",
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        if s:
            hd.update({'x-ladon': s.get("x-ladon", ""), 'x-khronos': s.get("x-khronos", ""), 'x-argus': s.get("x-argus", ""), 'x-gorgon': s.get("x-gorgon", ""), 'x-ss-req-ticket': s.get("x-ss-req-ticket", "")})
            if 'x-ss-stub' in s:
                hd['x-ss-stub'] = s['x-ss-stub']
        try:
            r = requests.post(url, params=prm, data=pl, headers=hd, timeout=10)
            if r.status_code == 200:
                res = r.json()
                return res.get('status_code') == 0
            else:
                return False
        except:
            return False
    
    def worker(self):
        while not self.stop_threads:
            try:
                u = self.queue.get(timeout=1)
                uid = u.get('uid', '')
                if uid:
                    ok = self.takipten_cik(uid)
                    if ok:
                        self.unfollowed += 1
                    else:
                        self.failed += 1
                self.queue.task_done()
            except queue.Empty:
                break
            except:
                self.queue.task_done()
                continue
    
    def tum_takip_edilenlerden_cik(self, kullanicilar):
        if not kullanicilar:
            return False
        self.total = len(kullanicilar)
        self.unfollowed = 0
        self.failed = 0
        for u in kullanicilar:
            self.queue.put(u)
        thread_sayisi = 5
        threads = []
        for i in range(thread_sayisi):
            t = threading.Thread(target=self.worker)
            t.daemon = True
            t.start()
            threads.append(t)
        self.queue.join()
        self.stop_threads = True
        for t in threads:
            t.join(timeout=2)
        return True

def verify_session(ses):
    try:
        reo = 'https://api16-normal-c-alisg.tiktokv.com/passport/web/account/info/'
        hes = {'Cookie': f'sessionid={ses}'}
        rer = requests.get(url=reo, headers=hes).json()
        if 'data' not in rer:
            return None
        idd = rer['data']['user_id']
        uss = rer['data']['username']
        return {'ses': ses, 'idd': idd, 'uss': uss}
    except:
        return None

def hide_video(ses, video_id):
    try:
        url = "https://api16-normal-c-alisg.tiktokv.com/aweme/v1/aweme/modify/visibility/"
        params = {
            'sss-network-channel': '9777763120734',
            'aweme_id': video_id,
            'type': '2',
            'request_tag_from': 'h5',
            'manifest_version_code': '370804',
            '_rticket': str(round(random.uniform(1.2, 1.6) * 100000000) * -1) + '5748',
            'app_language': 'ar',
            'app_type': 'normal',
            'iid': str(random.randint(1, 1019)),
            'app_package': 'com.zhiliaoapp.musically.go',
            'channel': 'googleplay',
            'device_type': 'RMX3710',
            'language': 'ar',
            'host_abi': 'arm64-v8a',
            'locale': 'ar',
            'resolution': '1080*2158',
            'openudid': str(binascii.hexlify(os.urandom(8)).decode()),
            'update_version_code': '370804',
            'ac2': 'wifi',
            'cdid': str(uuid.uuid4()),
            'sys_region': 'IQ',
            'os_api': '35',
            'timezone_name': 'Asia%2FBaghdad',
            'dpi': '480',
            'ac': 'wifi',
            'device_id': str(random.randint(1, 1019)),
            'os_version': '15',
            'timezone_offset': '10800',
            'version_code': '370804',
            'app_name': 'musically_go',
            'ab_version': '37.8.4',
            'version_name': '37.8.4',
            'device_brand': 'realme',
            'op_region': 'IQ',
            'ssmix': 'a',
            'device_platform': 'android',
            'build_number': '37.8.4',
            'region': 'IQ',
            'aid': '1340',
            'ts': str(round(random.uniform(1.2, 1.6) * 100000000) * -1),
        }
        params.update(SignerPy.get(params=params))
        headers = {
            'User-Agent': "com.zhiliaoapp.musically.go/370804 (Linux; U; Android 15; ar_IQ; RMX3710; Build/AP3A.240617.008;tt-ok/3.12.13.27-ul)",
            'Cookie': f"sessionid={ses};"
        }
        headers.update(SignerPy.sign(params=params))
        response = requests.get(url, params=params, headers=headers, timeout=10)
        return response.status_code == 200
    except:
        return False

def get_videos_list(ses, user_id, username):
    try:
        u = "https://api16-normal-c-alisg.tiktokv.com/lite/v2/public/item/list/"
        p = {
            'source': '0',
            'max_cursor': '0',
            'cursor': '0',
            'sec_user_id': user_id,
            'user_id': username,
            'count': '9',
            'filter_private': '1',
            'lite_flow_schedule': 'new',
            'cdn_cache_is_login': '1',
            'cdn_cache_strategy': 'v0',
            'manifest_version_code': '370804',
            '_rticket': '1764076129917',
            'app_language': 'ar',
            'app_type': 'normal',
            'iid': '7545453944668276487',
            'app_package': 'com.zhiliaoapp.musically.go',
            'channel': 'googleplay',
            'device_type': 'RMX3710',
            'language': 'ar',
            'host_abi': 'arm64-v8a',
            'locale': 'ar',
            'resolution': '1080*2158',
            'openudid': 'bd414b5aa37aa495',
            'update_version_code': '370804',
            'ac2': 'wifi',
            'cdid': 'a098bd2b-27e1-4435-bf83-934e23d091cb',
            'sys_region': 'IQ',
            'os_api': '35',
            'timezone_name': 'Asia%2FBaghdad',
            'dpi': '480',
            'ac': 'wifi',
            'device_id': '7545452907198875143',
            'os_version': '15',
            'timezone_offset': '10800',
            'version_code': '370804',
            'app_name': 'musically_go',
            'ab_version': '37.8.4',
            'version_name': '37.8.4',
            'device_brand': 'realme',
            'op_region': 'IQ',
            'ssmix': 'a',
            'device_platform': 'android',
            'build_number': '37.8.4',
            'region': 'IQ',
            'aid': '1340',
            'ts': '1764060062'
        }
        p.update(SignerPy.get(params=p))
        h = {
            'User-Agent': "com.zhiliaoapp.musically.go/370804 (Linux; U; Android 15; ar_IQ; RMX3710; Build/AP3A.240617.008;tt-ok/3.12.13.27-ul)",
            'Cookie': f"sessionid={ses};"
        }
        h.update(SignerPy.sign(params=p))
        r = requests.get(url=u, params=p, headers=h, timeout=10).json()
        if 'aweme_list' in r:
            videos = [video['aweme_id'] for video in r['aweme_list']]
            return videos
        return []
    except:
        return []

def get_reposts_batch(session_id, user_id):
    try:
        params = {
            'user_id': user_id,
            'offset': '0',
            'count': '20',
            'scene': '0',
            'manifest_version_code': '370804',
            '_rticket': '1764060071228',
            'app_language': 'ar',
            'app_type': 'normal',
            'iid': '7545453944668276487',
            'app_package': 'com.zhiliaoapp.musically.go',
            'channel': 'googleplay',
            'device_type': 'RMX3710',
            'language': 'ar',
            'host_abi': 'arm64-v8a',
            'locale': 'ar',
            'resolution': '1080*2158',
            'openudid': 'bd414b5aa37aa495',
            'update_version_code': '370804',
            'ac2': 'wifi',
            'cdid': 'a098bd2b-27e1-4435-bf83-934e23d091cb',
            'sys_region': 'IQ',
            'os_api': '35',
            'timezone_name': 'Asia%2FBaghdad',
            'dpi': '480',
            'ac': 'wifi',
            'device_id': '7545452907198875143',
            'os_version': '15',
            'timezone_offset': '10800',
            'version_code': '370804',
            'app_name': 'musically_go',
            'ab_version': '37.8.4',
            'version_name': '37.8.4',
            'device_brand': 'realme',
            'op_region': 'IQ',
            'ssmix': 'a',
            'device_platform': 'android',
            'build_number': '37.8.4',
            'region': 'IQ',
            'aid': '1340',
            'ts': '1764060062'
        }
        params.update(SignerPy.get(params=params))
        headers = {
            'User-Agent': "com.zhiliaoapp.musically.go/370804 (Linux; U; Android 15; ar_IQ; RMX3710; Build/AP3A.240617.008;tt-ok/3.12.13.27-ul)",
            'Cookie': f"sessionid={session_id};"
        }
        headers.update(SignerPy.sign(params=params))
        url = "https://api16-normal-c-alisg.tiktokv.com/tiktok/v1/upvote/item/list"
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'aweme_list' in data:
                return data['aweme_list']
    except:
        pass
    return []

def delete_single_repost(session_id, item_id):
    try:
        params = {
            'manifest_version_code': '370804',
            '_rticket': str(round(random.uniform(1.2, 1.6) * 100000000) * -1) + "1228",
            'app_language': 'ar',
            'app_type': 'normal',
            'iid': '7545453944668276487',
            'app_package': 'com.zhiliaoapp.musically.go',
            'channel': 'googleplay',
            'device_type': 'RMX3710',
            'language': 'ar',
            'host_abi': 'arm64-v8a',
            'locale': 'ar',
            'resolution': '1080*2158',
            'openudid': str(binascii.hexlify(os.urandom(8)).decode()),
            'update_version_code': '370804',
            'ac2': 'wifi',
            'cdid': str(uuid.uuid4()),
            'sys_region': 'IQ',
            'os_api': '35',
            'timezone_name': 'Asia%2FBaghdad',
            'dpi': '480',
            'ac': 'wifi',
            'device_id': str(random.randint(1, 10**19)),
            'os_version': '15',
            'timezone_offset': '10800',
            'version_code': '370804',
            'app_name': 'musically_go',
            'ab_version': '37.8.4',
            'version_name': '37.8.4',
            'device_brand': 'realme',
            'op_region': 'IQ',
            'ssmix': 'a',
            'device_platform': 'android',
            'build_number': '37.8.4',
            'region': 'IQ',
            'aid': '1340',
            'ts': str(round(random.uniform(1.2, 1.6) * 100000000) * -1)
        }
        params.update(SignerPy.get(params=params))
        data = {'item_id': item_id}
        headers = {
            'User-Agent': "com.zhiliaoapp.musically.go/370804 (Linux; U; Android 15; ar_IQ; RMX3710; Build/AP3A.240617.008;tt-ok/3.12.13.27-ul)",
            'Cookie': f"sessionid={session_id};"
        }
        headers.update(SignerPy.sign(params=params))
        url = "https://api16-normal-c-alisg.tiktokv.com/tiktok/v1/upvote/delete"
        response = requests.post(url, params=params, data=data, headers=headers, timeout=10)
        return response.status_code == 200
    except:
        return False

def get_collect_list(session_id):
    url = "https://www.tiktok.com/api/user/collect/item_list/"
    params = {
        "WebIdLastTime": "1770134387",
        "aid": "1988",
        "app_language": "en",
        "app_name": "tiktok_web",
        "browser_language": "en-US",
        "browser_name": "Mozilla",
        "browser_online": "true",
        "browser_platform": "Win32",
        "browser_version": "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "channel": "tiktok_web",
        "cookie_enabled": "true",
        "count": "16",
        "coverFormat": "2",
        "cursor": "0",
        "data_collection_enabled": "true",
        "device_id": "7602669281545553426",
        "device_platform": "web_pc",
        "focus_state": "true",
        "from_page": "user",
        "history_len": "4",
        "is_fullscreen": "false",
        "is_page_visible": "true",
        "language": "en",
        "needPinnedItemIds": "true",
        "odinId": "7176740807839466501",
        "os": "windows",
        "post_item_list_request_type": "0",
        "priority_region": "EG",
        "referer": "",
        "region": "EG",
        "screen_height": "900",
        "screen_width": "1440",
        "secUid": "MS4wLjABAAAAvU_mnlMFa1U90APPuhamoipwrfoNGJlG3TnZVx8-reB3NHMv8Ndrwrm6gBJ-zMY7",
        "tz_name": "Africa/Cairo",
        "user_is_login": "true",
        "video_encoding": "mp4",
        "webcast_language": "en"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "Referer": "https://www.tiktok.com/",
        "cookie": f"sessionid={session_id}"
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            items = data.get("itemList", [])
            result = []
            for item in items:
                try:
                    result.append({"id": item["id"], "nickname": item["author"]["nickname"]})
                except:
                    pass
            return result
    except:
        pass
    return []

def delete_collect_item(session_id, aweme_id):
    device_id = str(random.randint(10**18, 10**19 - 1))
    url = "https://aggr32-normal.tiktokv.com/aweme/v1/aweme/collect/"
    params = {
        'aweme_id': aweme_id,
        'action': "0",
        'collect_privacy_setting': "0",
        'device_platform': "android",
        'os': "android",
        'ssmix': "a",
        '_rticket': str(int(time.time() * 1000)),
        'channel': "googleplay",
        'aid': "1233",
        'app_name': "musical_ly",
        'version_code': "430504",
        'version_name': "43.5.4",
        'manifest_version_code': "2024305040",
        'update_version_code': "2024305040",
        'ab_version': "43.5.4",
        'resolution': "720*1504",
        'dpi': "320",
        'device_type': "RMX3263",
        'device_brand': "realme",
        'language': "ar",
        'os_api': "30",
        'os_version': "11",
        'ac': "wifi",
        'is_pad': "0",
        'current_region': "EG",
        'app_type': "normal",
        'sys_region': "EG",
        'last_install_time': "1770546646",
        'mcc_mnc': "60202",
        'timezone_name': "Africa/Cairo",
        'carrier_region_v2': "602",
        'residence': "EG",
        'app_language': "ar",
        'carrier_region': "EG",
        'timezone_offset': "7200",
        'host_abi': "arm64-v8a",
        'locale': "ar",
        'ac2': "wifi",
        'uoo': "0",
        'op_region': "EG",
        'build_number': "43.5.4",
        'region': "EG",
        'ts': str(int(time.time())),
        'iid': device_id,
        'device_id': device_id
    }
    headers = {
        'User-Agent': "com.zhiliaoapp.musically/2024305040 (Linux; U; Android 11; ar; RMX3263; Build/RP1A.201005.001; Cronet/TTNetVersion:82120377 2026-01-13 QuicVersion:5f252c33 2025-12-30)",
        'x-tt-pba-enable': "1",
        'traceparent': "unsampled_ttk_trace_span_80812822-00",
        'x-bd-kmsv': "0",
        'x-tt-dm-status': "login=1;ct=1;rt=1",
        'x-ss-req-ticket': "1770590992181",
        'x-opti-ut': "ClGyIDxzzE4CyNOa1Z2Rr6MLsAlgPtfigtPXLJMEEgzWhG3sMrzJ0mKI1cRfAuF5uV9JHU1XBAGcNASZdNqMqUmC-taDLgD1Rt4YBzTtKOl82H4aSQo8AAAAAAAAAAAAAFAM1AiI_NDwEOvaluOtC3NmIIpP9Sy01GmKQpin285g6rVPpcevo_8YBwhZUAcHY9YgEPePiQ4YxLzzlg0iAQTghEqn",
        'tt-ticket-guard-public-key': "BF2Qho1dahaRgySXandIUoXo8HtLRSvwJWCfizVstnLqNH2YceIISmiaGgEfsRIcCUYV2a/dqirCo5EIHm2I1uI=",
        'sdk-version': "2",
        'tt-ticket-guard-iteration-version': "0",
        'tt-ticket-guard-client-data': "eyJyZXFfY29udGVudCI6InRpY2tldCxwYXRoLHRpbWVzdGFtcCIsInJlcV9zaWduIjoiTUVVQ0lRQ3R0MmdCTzRCYjhJd0JjNnh0ZUJxNVEwem5SU1A4eHZhY1dVR010dWxyd2dJZ1lndi81Wm5iNWllU2toQ2Iyc2hSVU80aWtmMFhGQS9HcUt5Qkt0eTg3c2tcdTAwM2QiLCJ0aW1lc3RhbXAiOjE3NzA1OTA5OTIsInRzX3NpZ24iOiJ0cy4xLjE3YmNkZGY1ZDcwMmQyYjBjNGViZjYzZmEzMmMwODZlZWFiNTljMGUwMzRmYTgxZDkzN2YyZjZlMjE0NmVmNjYwZTcwYjRiZGE4MmMxMzgzNmU1Y2ZhMTgzOTRkNzAyNDBmOGFmMTYzMWYxNjVhZTk2MDEyMmVlZmZkNDUzM2RkIn0=",
        'x-tt-token': "0385152b0c24a3e6169c9bbb4f83b42bb0017c626ef79412c576ca08932bc0e536c15ca0f08fe9874ef76829c02efdef83b5ccc9eea79183365938e476c5368e9d64139e2a632732caaf54def734fd5d05f60567bad26e0040c8ae8a95358cc0e26de--0a4e0a2030f09bf15ab6a7858e165a77200d7e988aaa279d45496cb2c30032486758b36e12200a34264ce7f0751b609e5ba58bedfd2e584db9ba6d4bc80acc41550e6468a0751801220674696b746f6b-3.0.1",
        'tt-ticket-guard-version': "3",
        'passport-sdk-version': "1",
        'oec-cs-si-a': "2",
        'oec-cs-sdk-version': "v10.02.00-ov-android_V31",
        'x-vc-bdturing-sdk-version': "2.3.17.i18n",
        'rpc-persist-pns-region-1': "EG|357994",
        'rpc-persist-pns-region-2': "EG|357994",
        'rpc-persist-pns-region-3': "EG|357994|360016",
        'oec-vc-sdk-version': "3.2.1.i18n",
        'x-tt-request-tag': "n=0;nr=011;bg=0;s=-1;p=0",
        'x-tt-store-region': "eg",
        'x-tt-store-region-src': "uid",
        'rpc-persist-pyxis-policy-v-tnc': "1",
        'x-tt-ttnet-origin-host': "api31-normal-alisg.tiktokv.com",
        'x-ss-dp': "1233",
        'Cookie': f"sessionid={session_id}"
    }
    try:
        params = SignerPy.get(params=params)
        signature = SignerPy.sign(params=params)
        headers.update({
            'x-ss-req-ticket': signature['x-ss-req-ticket'],
            'x-ss-stub': signature['x-ss-stub'],
            'x-argus': signature["x-argus"],
            'x-gorgon': signature["x-gorgon"],
            'x-khronos': signature["x-khronos"],
            'x-ladon': signature["x-ladon"],
        })
        res = requests.post(url, params=params, headers=headers, timeout=10)
        return res.status_code == 200
    except:
        return False

user_states = {}
user_lang = {}
user_sessions = {}
delete_in_progress = {}
hide_in_progress = {}
unfollow_in_progress = {}
favorites_in_progress = {}

@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id
    user = message.from_user
    cid = chat_id
    
    update_stats(cid, "start")
    
    banned = load("banned")
    if cid in banned:
        return
    
    users = load("users")
    if cid not in users:
        users.append(cid)
        save("users", users)
        
        notified = load("notified")
        if cid not in notified:
            notified.append(cid)
            save("notified", notified)
            username_str = f"@{user.username}" if user.username else "لا يوجد"
            send_message(ADMIN_ID, f"- New user\n- Name : {user.first_name}\n- Username : {username_str}\n- ID : {cid}\n- Total number of members : {len(users)}")
    
    if not is_subscribed(cid):
        bot.send_message(cid, T(cid, "اشترك بالقنوات اولاً", "Subscribe to channels first"), reply_markup=force_markup_lang(cid))
        return

    if cid == ADMIN_ID:
        bot.send_message(cid, "لوحة الادمن", reply_markup=admin_markup_new())
    else:
        if cid not in user_lang:
            bot.send_message(cid, "اختر لغتك / Choose your language", reply_markup=lang_markup())
        else:
            bot.send_message(cid, "💙 تحية ملؤها التقدير والاحترام 💙\n\n💠 نورتنا بحضورك المميز 💠\n❄️ نتمنى لك تجربة رائعة ومفيدة ❄️\n\n🧿 مع تحيات المطور غلام @M_321 🧿\n\nاختر من القائمة اولاً", reply_markup=main_markup_new(cid))

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    cid = call.message.chat.id
    data = call.data
    
    if data == "set_lang_ar":
        user_lang[cid] = "ar"
        try:
            bot.delete_message(cid, call.message.message_id)
        except:
            pass
        if not is_subscribed(cid):
            bot.send_message(cid, T(cid, "اشترك بالقنوات اولاً", "Subscribe first"), reply_markup=force_markup_lang(cid))
        else:
            bot.send_message(cid, "💙 تحية ملؤها التقدير والاحترام 💙\n\n💠 نورتنا بحضورك المميز 💠\n❄️ نتمنى لك تجربة رائعة ومفيدة ❄️\n\n🧿 مع تحيات المطور غلام @M_321 🧿\n\nاختر من القائمة اولاً", reply_markup=main_markup_new(cid))
        return

    if data == "set_lang_en":
        user_lang[cid] = "en"
        try:
            bot.delete_message(cid, call.message.message_id)
        except:
            pass
        if not is_subscribed(cid):
            bot.send_message(cid, T(cid, "اشترك بالقنوات اولاً", "Subscribe first"), reply_markup=force_markup_lang(cid))
        else:
            bot.send_message(cid, "💙 تحية ملؤها التقدير والاحترام 💙\n\n💠 نورتنا بحضورك المميز 💠\n❄️ نتمنى لك تجربة رائعة ومفيدة ❄️\n\n🧿 مع تحيات المطور غلام @M_321 🧿\n\nاختر من القائمة اولاً", reply_markup=main_markup_new(cid))
        return

    if data == "check":
        if is_subscribed(cid):
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            if cid == ADMIN_ID:
                bot.send_message(cid, "لوحة الادمن", reply_markup=admin_markup_new())
            elif cid not in user_lang:
                bot.send_message(cid, "اختر لغتك / Choose your language", reply_markup=lang_markup())
            else:
                bot.send_message(cid, "💙 تحية ملؤها التقدير والاحترام 💙\n\n💠 نورتنا بحضورك المميز 💠\n❄️ نتمنى لك تجربة رائعة ومفيدة ❄️\n\n🧿 مع تحيات المطور غلام @M_321 🧿\n\nاختر من القائمة اولاً", reply_markup=main_markup_new(cid))
        else:
            bot.answer_callback_query(call.id, T(cid, "اشترك اولاً", "Subscribe first"))
        return
    
    elif data == "change_lang":
        try:
            bot.delete_message(cid, call.message.message_id)
        except:
            pass
        bot.send_message(cid, "اختر لغتك / Choose your language", reply_markup=lang_markup())
        return

    elif data == "go_back":
        if cid in user_states:
            del user_states[cid]
        try:
            bot.delete_message(cid, call.message.message_id)
        except:
            pass
        bot.send_message(cid, "💙 تحية ملؤها التقدير والاحترام 💙\n\n💠 نورتنا بحضورك المميز 💠\n❄️ نتمنى لك تجربة رائعة ومفيدة ❄️\n\n🧿 مع تحيات المطور غلام @M_321 🧿\n\nاختر من القائمة اولاً", reply_markup=main_markup_new(cid))
        return

    elif data == "session":
        user_states[cid] = "wait_session"
        try:
            bot.delete_message(cid, call.message.message_id)
        except:
            pass
        bot.send_message(cid, T(cid, "- ارسل السيشن :", "- Send the session :"), reply_markup=back_markup(cid))
        return
    
    elif data == "username":
        user_states[cid] = "wait_username"
        try:
            bot.delete_message(cid, call.message.message_id)
        except:
            pass
        bot.send_message(cid, T(cid, "- ارسل اليوزر :", "- Send the username :"), reply_markup=back_markup(cid))
        return
    
    elif data == "check_bindings":
        user_states[cid] = "wait_bindings"
        try:
            bot.delete_message(cid, call.message.message_id)
        except:
            pass
        bot.send_message(cid, T(cid, "- ارسل اليوزر :", "- Send the username :"), reply_markup=back_markup(cid))
        return
    
    elif data == "wallet":
        user_states[cid] = "wait_wallet"
        try:
            bot.delete_message(cid, call.message.message_id)
        except:
            pass
        bot.send_message(cid, T(cid, "- ارسل السيشن :", "- Send the session :"), reply_markup=back_markup(cid))
        return
    
    elif data == "unfollow":
        user_states[cid] = "wait_unfollow"
        try:
            bot.delete_message(cid, call.message.message_id)
        except:
            pass
        bot.send_message(cid, T(cid, "- ارسل السيشن :", "- Send the session :"), reply_markup=back_markup(cid))
        return
    
    elif data == "unfollow_all":
        user_states[cid] = "wait_unfollow_all"
        try:
            bot.delete_message(cid, call.message.message_id)
        except:
            pass
        bot.send_message(cid, T(cid, "- ارسل السيشن :", "- Send the session :"), reply_markup=back_markup(cid))
        return
    
    elif data == "hide_videos":
        user_states[cid] = "wait_hide"
        try:
            bot.delete_message(cid, call.message.message_id)
        except:
            pass
        bot.send_message(cid, T(cid, "- ارسل السيشن :", "- Send the session :"), reply_markup=back_markup(cid))
        return
    
    elif data == "delete_reposts":
        user_states[cid] = "wait_reposts"
        try:
            bot.delete_message(cid, call.message.message_id)
        except:
            pass
        bot.send_message(cid, T(cid, "- ارسل السيشن :", "- Send the session :"), reply_markup=back_markup(cid))
        return
    
    elif data == "delete_favorites":
        user_states[cid] = "wait_favorites"
        try:
            bot.delete_message(cid, call.message.message_id)
        except:
            pass
        bot.send_message(cid, T(cid, "- ارسل السيشن :", "- Send the session :"), reply_markup=back_markup(cid))
        return

    if cid == ADMIN_ID:
        if data == "admin_stats":
            users = load("users")
            banned = load("banned")
            stats = load_stats()
            
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            yesterday = (datetime.datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            this_month = datetime.datetime.now().strftime("%Y-%m")
            last_month = (datetime.datetime.now() - timedelta(days=30)).strftime("%Y-%m")
            
            today_stats = stats["daily"].get(today, {"users": 0, "starts": 0, "messages": 0})
            yesterday_stats = stats["daily"].get(yesterday, {"users": 0, "starts": 0, "messages": 0})
            
            new_today = 0
            new_yesterday = 0
            new_this_month = 0
            new_last_month = 0
            
            for uid, date in stats.get("started_users", {}).items():
                if date == today:
                    new_today += 1
                if date == yesterday:
                    new_yesterday += 1
                if date.startswith(this_month):
                    new_this_month += 1
                if date.startswith(last_month):
                    new_last_month += 1
            
            stats_text = f"""احصائيات البوت:

المستخدمون:
- العدد الإجمالي للمستخدمين: {len(users)}
- عدد المستخدمين في الخاص: {len(users)}
- عدد القنوات والمجموعات: 0
- عدد المحظورين: {len(banned)}

التفاعل:
- اليوم ({today}):
  - المستخدمون: {today_stats.get('users', 0)}
  - بداية الاشتراك: {today_stats.get('starts', 0)}
  - الرسائل: {today_stats.get('messages', 0)}

- في الأمس ({yesterday}):
  - المستخدمون: {yesterday_stats.get('users', 0)}
  - بداية الاشتراك: {yesterday_stats.get('starts', 0)}
  - الرسائل: {yesterday_stats.get('messages', 0)}

- عدد المستخدمين الجدد اليوم: {new_today}
- عدد المستخدمين الجدد بالأمس: {new_yesterday}
- عدد المستخدمين الجدد هذا الشهر: {new_this_month}
- عدد المستخدمين الجدد في الشهر الماضي: {new_last_month}"""
            
            bot.send_message(cid, stats_text)
            return
        
        elif data == "admin_broadcast_users":
            user_states[cid] = "admin_broadcast_users"
            bot.send_message(cid, "ارسل نص الاذاعة للمستخدمين")
            return
        
        elif data == "admin_broadcast_channels":
            user_states[cid] = "admin_broadcast_channels"
            bot.send_message(cid, "ارسل نص الاذاعة للقنوات")
            return
        
        elif data == "admin_broadcast_groups":
            user_states[cid] = "admin_broadcast_groups"
            bot.send_message(cid, "ارسل نص الاذاعة للمجموعات")
            return
        
        elif data == "admin_ban":
            user_states[cid] = "admin_ban"
            bot.send_message(cid, "ارسل ايدي المستخدم للحظر")
            return
        
        elif data == "admin_unban":
            user_states[cid] = "admin_unban"
            bot.send_message(cid, "ارسل ايدي المستخدم لفك الحظر")
            return
        
        elif data == "admin_banned_list":
            banned = load("banned")
            if banned:
                bot.send_message(cid, f"المستخدمون المحظورون:\n" + "\n".join([str(uid) for uid in banned]))
            else:
                bot.send_message(cid, "لا يوجد مستخدمين محظورين")
            return

@bot.message_handler(func=lambda message: True)
def message_handler(message):
    cid = message.chat.id
    txt = message.text.strip()
    user = message.from_user
    
    banned = load("banned")
    if cid in banned:
        return
    
    users = load("users")
    if cid not in users:
        users.append(cid)
        save("users", users)
    
    update_stats(cid, "message")
    
    if not is_subscribed(cid):
        bot.send_message(cid, T(cid, "اشترك بالقنوات اولاً", "Subscribe to channels first"), reply_markup=force_markup_lang(cid))
        return
    
    if cid in user_states:
        state = user_states[cid]
        
        if state == "wait_session":
            del user_states[cid]
            ses = info_session(txt)
            if not ses:
                bot.send_message(cid, "سيشن غير صالح")
                return
            try:
                info = ms4.InfoTik.TikTok_Info(ses["username"])
                level = lev(info.get("id"))
            except:
                info = {"name": "", "followers": "", "following": "", "like": "", "video": "", "country": "", "bio": "", "private": "", "id": ""}
                level = "None"
            coins, money = gets_mony(txt)
            bot.send_message(cid, f"""
- Username : {ses['username']}
- Name : {info.get('name')}
- iD : {info.get('id')}
- Level : {level}
- Followers {info.get('followers')}
- Foloowing : {info.get('following')}
- Likes : {info.get('like')}
- Country : {info.get('country')}
- Videos : {info.get('video')}
- Private : {info.get('private')}
- Bio : {info.get('bio')}
- Coins : {coins}
- Money : {money}
- Email : {ses['email']}
- Mobile : {ses['mobile']}
- Verified : {ses['user_verified']}
- Has Password : {ses['has_password']}
- Sec User iD : {ses['sec_user_id']}
""")
            return

        elif state == "wait_username":
            del user_states[cid]
            info = info_by_username(txt)
            if info:
                bot.send_message(cid, json.dumps(info, ensure_ascii=False, indent=2))
            else:
                bot.send_message(cid, "فشل في جلب المعلومات. تأكد من صحة اليوزر أو حاول مرة أخرى لاحقاً.")
            return

        # ========== الجزء المعدل ==========
        elif state == "wait_bindings":
            del user_states[cid]
            bot.send_message(cid, "🔍 جاري البحث عن ربطات الحساب...")
            result = find_account_end_point(txt)  # استخدم الدالة الأصلية
            
            if result and result.get('data'):
                data = result['data']
                email_status = "✅" if data.get('has_email') else "❌"
                phone_status = "✅" if data.get('has_mobile') else "❌"
                oauth_status = "✅" if data.get('has_oauth') else "❌"
                passkey_status = "✅" if data.get('has_passkey') else "❌"
                response = f"Email : {email_status}\nPhone : {phone_status}\nOAuth : {oauth_status}\nPasskey : {passkey_status}"
                platforms = data.get('oauth_platforms', [])
                if platforms:
                    response += f"\nPlatforms : {', '.join(platforms)}"
                response += "\nLevel : غير متاح"
            else:
                response = "Failed. Recheck the username or try again later."
            bot.send_message(cid, response)
            return
        # ========== نهاية الجزء المعدل ==========
        
        elif state == "wait_wallet":
            del user_states[cid]
            coins, money = gets_mony(txt)
            if coins == 0 and money == 0:
                bot.send_message(cid, "- ❌ | The session is invalid..")
            else:
                bot.send_message(cid, f"""
- Coins : {coins}
- Money : {money}
""")
            return

        elif state == "wait_unfollow" or state == "wait_unfollow_all":
            del user_states[cid]
            if cid in unfollow_in_progress:
                bot.send_message(cid, "⚠️ جارٍ بالفعل عملية الغاء متابعة")
                return
            unfollow_in_progress[cid] = True
            
            bot.send_message(cid, "جاري التحقق من السيشن...")
            karbo = karboxTool(txt)
            kullanici = karbo.kullanici_bilgisi_sessiondan()
            
            if not kullanici:
                bot.send_message(cid, "• السيشن غير شغال")
                del unfollow_in_progress[cid]
                return
            
            bot.send_message(cid, f"تم التحقق بنجاح!\nالحساب: @{kullanici['username']}\n\nجاري جلب قائمة المتابعين...")
            
            liste = karbo.tum_takip_edilenleri_cek(kullanici['uid'], kullanici['sec'])
            
            if not liste:
                bot.send_message(cid, "لا يوجد متابعين أو حدث خطأ في جلب القائمة")
                del unfollow_in_progress[cid]
                return
            
            bot.send_message(cid, f"تم العثور على {len(liste)} متابع\nجاري إلغاء المتابعة...")
            
            karbo.tum_takip_edilenlerden_cik(liste)
            
            result_message = f"تم الإنتهاء!\n✅ {karbo.unfollowed} نجاح\n❌ {karbo.failed} فشل"
            bot.send_message(cid, result_message)
            del unfollow_in_progress[cid]
            return

        elif state == "wait_hide":
            del user_states[cid]
            if cid in hide_in_progress:
                bot.send_message(cid, "⚠️ جارٍ بالفعل اخفاء الفيديوهات")
                return
            hide_in_progress[cid] = True
            
            bot.send_message(cid, "جارٍ التحقق من السيشن...")
            user_info = verify_session(txt)
            
            if not user_info:
                bot.send_message(cid, "❌ السيشن غير صالح")
                del hide_in_progress[cid]
                return
            
            bot.send_message(cid, f"✅ تم التحقق من الحساب\n👤 المعرف: {user_info['idd']}\n📛 اليوزر: {user_info['uss']}")
            
            bot.send_message(cid, "جارٍ إخفاء الفيديوهات...")
            videos = get_videos_list(txt, user_info['idd'], user_info['uss'])
            
            if not videos:
                bot.send_message(cid, "❌ لم يتم العثور على فيديوهات")
                del hide_in_progress[cid]
                return
            
            total_videos = len(videos)
            hidden_count = 0
            
            bot.send_message(cid, f"📹 تم العثور على {total_videos} فيديو")
            
            for i, video_id in enumerate(videos, 1):
                if hide_video(txt, video_id):
                    hidden_count += 1
                if i % 3 == 0:
                    bot.send_message(cid, f"⏳ جاري العمل... {i}/{total_videos}")
                time.sleep(0.7)
            
            bot.send_message(cid, f"✅ تم إخفاء {hidden_count} فيديو")
            del hide_in_progress[cid]
            return
        
        elif state == "wait_reposts":
            del user_states[cid]
            if cid in delete_in_progress:
                bot.send_message(cid, "- ❌ ¦- عذرا هنالك عملية حذف جارية..")
                return
            delete_in_progress[cid] = True
            
            bot.send_message(cid, "🕜¦- جاري التحقق من السيشن..")
            check_url = 'https://api16-normal-c-alisg.tiktokv.com/passport/web/account/info/'
            headers = {'Cookie': f'sessionid={txt}'}
            
            try:
                response = requests.get(check_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    user_id = data.get('data', {}).get('user_id')
                    if user_id:
                        bot.send_message(cid, "📊 ¦ - جارِ حسب الريبوستات")
                        deleted_count = 0
                        
                        while True:
                            reposts = get_reposts_batch(txt, user_id)
                            if not reposts or len(reposts) == 0:
                                break
                            for item in reposts:
                                success = delete_single_repost(txt, item['aweme_id'])
                                if success:
                                    deleted_count += 1
                                if deleted_count % 75 == 0:
                                    bot.send_message(cid, f"- 🕜 ¦- جارِ الحذف\n✅ ¦ - تم حذف = [ {deleted_count} ] ريبوست")
                                time.sleep(0.3)
                            if len(reposts) < 75:
                                break
                        
                        bot.send_message(cid, f"- ✅ ¦ - تم حذف = [ {deleted_count} ]")
                    else:
                        bot.send_message(cid, "- ❌ ¦- السيشن غير شغال...")
                else:
                    bot.send_message(cid, "- ❌ ¦- حدث خطا اثناء الاتصال بالسيشن..")
            except Exception as e:
                bot.send_message(cid, f"- ❌ ¦- حدث خطا: {str(e)}")
            
            del delete_in_progress[cid]
            return
        
        elif state == "wait_favorites":
            del user_states[cid]
            if cid in favorites_in_progress:
                bot.send_message(cid, "⚠️ جارٍ بالفعل حذف المفضلة")
                return
            favorites_in_progress[cid] = True
            
            bot.send_message(cid, "Fetching your collected posts, please wait...")
            posts = get_collect_list(txt)
            
            if not posts:
                bot.send_message(cid, "Error: No posts found or invalid sessionid.")
                del favorites_in_progress[cid]
                return
            
            bot.send_message(cid, f"Found {len(posts)} posts. How many do you want to delete?")
            bot.register_next_step_handler(message, lambda msg: process_favorites_deletion(msg, txt, posts))
            return
        
        elif cid == ADMIN_ID:
            if state == "admin_broadcast_users":
                del user_states[cid]
                users_list = load("users")
                success = 0
                failed = 0
                for uid in users_list:
                    try:
                        bot.send_message(uid, txt)
                        success += 1
                        time.sleep(0.05)
                    except:
                        failed += 1
                bot.send_message(cid, f"تم الاذاعة\n✅ نجاح: {success}\n❌ فشل: {failed}")
                return
            
            elif state == "admin_broadcast_channels":
                del user_states[cid]
                bot.send_message(cid, "هذه الخدمة قيد التطوير")
                return
            
            elif state == "admin_broadcast_groups":
                del user_states[cid]
                bot.send_message(cid, "هذه الخدمة قيد التطوير")
                return
            
            elif state == "admin_ban":
                del user_states[cid]
                try:
                    uid = int(txt)
                    banned = load("banned")
                    if uid not in banned:
                        banned.append(uid)
                        save("banned", banned)
                    bot.send_message(cid, "تم الحظر")
                except:
                    bot.send_message(cid, "ايدي غير صالح")
                return
            
            elif state == "admin_unban":
                del user_states[cid]
                try:
                    uid = int(txt)
                    banned = load("banned")
                    if uid in banned:
                        banned.remove(uid)
                        save("banned", banned)
                    bot.send_message(cid, "تم فك الحظر")
                except:
                    bot.send_message(cid, "ايدي غير صالح")
                return
    
    else:
        if txt.startswith('/'):
            return
        bot.send_message(cid, "💙 تحية ملؤها التقدير والاحترام 💙\n\n💠 نورتنا بحضورك المميز 💠\n❄️ نتمنى لك تجربة رائعة ومفيدة ❄️\n\n🧿 مع تحيات المطور غلام @M_321 🧿\n\nاختر من القائمة اولاً", reply_markup=main_markup_new(cid))

def process_favorites_deletion(message, session_id, posts):
    cid = message.chat.id
    try:
        amount = int(message.text.strip())
        posts_to_del = posts[:amount]
        bot.send_message(cid, f"Starting deletion of {len(posts_to_del)} posts...")
        success_count = 0
        fail_count = 0
        for p in posts_to_del:
            success = delete_collect_item(session_id, p['id'])
            if success:
                success_count += 1
            else:
                fail_count += 1
            time.sleep(0.5)
        bot.send_message(cid, f"Task Finished!\n✅ Success: {success_count}\n❌ Failed: {fail_count}")
    except ValueError:
        bot.send_message(cid, "Please enter a valid number.")
    except Exception as e:
        bot.send_message(cid, f"حدث خطأ: {str(e)}")
    finally:
        if cid in favorites_in_progress:
            del favorites_in_progress[cid]

def get_level(username):
    try:
        r = requests.get(f"https://www.tiktok.com/@{username}", headers={"User-Agent": "Mozilla/5.0"}).text
        g = r.split('webapp.user-detail"')[1].split('"RecommendUserList"')[0]
        
        def get_val(k, end='",'):
            try:
                return g.split(f'{k}":"')[1].split(end)[0]
            except:
                return ""
        
        uid = get_val("id")
        if uid:
            return lev(uid)
    except:
        pass
    return None

# ========== دالة تشغيل Flask ==========
def run_flask():
    """تشغيل سيرفر Flask في خلفية منفصلة"""
    logger.info("🚀 بدء تشغيل سيرفر Flask على المنفذ 12703...")
    try:
        flask_app.run(host='0.0.0.0', port=12703, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        logger.error(f"خطأ في تشغيل سيرفر Flask: {e}")

# ========== دالة مراقبة البوت ==========
def monitor_bot():
    """مراقبة حالة البوت بشكل دوري"""
    while True:
        try:
            users_list = load("users")
            flask_status["bot_users"] = len(users_list)
            flask_status["running"] = True
            logger.info(f"📊 مراقبة البوت: {flask_status['bot_users']} مستخدم نشط")
            time.sleep(60)
        except Exception as e:
            logger.error(f"خطأ في المراقبة: {e}")
            time.sleep(10)

# ========== التشغيل الرئيسي ==========
if __name__ == "__main__":
    try:
        flask_thread = threading.Thread(target=run_flask, daemon=True, name="FlaskServer")
        flask_thread.start()
        logger.info("✅ تم تشغيل سيرفر Flask في الخلفية")
        
        time.sleep(2)
        
        monitor_thread = threading.Thread(target=monitor_bot, daemon=True, name="BotMonitor")
        monitor_thread.start()
        logger.info("✅ تم تشغيل نظام المراقبة")
        
        print("\n" + "="*60)
        print("🤖 البوت يعمل الآن بنجاح!")
        print("="*60)
        print("📍 Flask API:")
        print(f"   - الرئيسية: http://localhost:12703/")
        print(f"   - الحالة: http://localhost:12703/status")
        print(f"   - اختبار: http://localhost:12703/ping")
        print("="*60)
        print("📱 بوت تيليجرام يعمل:")
        print(f"   - المطور: @M_321")
        print("="*60)
        print("💡 اضغط Ctrl+C لإيقاف البوت")
        print("="*60 + "\n")
        
        # ========== الجزء المعدل: تشغيل البوت بدون توقف ==========
        while True:
            try:
                bot.polling(non_stop=True, timeout=60, long_polling_timeout=60)
            except Exception as e:
                logger.error(f"خطأ في البوت: {e}")
                logger.info("جاري إعادة تشغيل البوت خلال 5 ثوان...")
                time.sleep(5)
        # ========== نهاية الجزء المعدل ==========
        
    except KeyboardInterrupt:
        print("\n")
        logger.info("⚠️ تم الضغط على Ctrl+C - جاري إيقاف البوت...")
        flask_status["running"] = False
        logger.info("✅ تم إيقاف البوت بنجاح")
        
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {e}")
        
    finally:
        logger.info("👋 تم إغلاق البوت")