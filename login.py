# login.py

import requests
from config import WEIBO_USERNAME, WEIBO_PASSWORD

def login():
    session = requests.Session()
    login_url = "https://passport.weibo.cn/sso/signin"
    data = {
        "username": WEIBO_USERNAME,
        "password": WEIBO_PASSWORD,
        "savestate": "1",
        "entry": "miniblog",
        "mainpageflag": "1",
    }
    response = session.post(login_url, data=data)
    if response.status_code == 200:
        return session
    else:
        raise Exception("Login failed")