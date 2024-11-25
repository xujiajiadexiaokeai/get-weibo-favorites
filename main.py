# main.py

import schedule
import time
from login import login
from weibo_crawler import get_weibo_fav
from database import create_table
from config import SCHEDULE_INTERVAL

def job():
    session = login()
    get_weibo_fav(session)

def main():
    create_table()
    schedule.every(SCHEDULE_INTERVAL).do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()