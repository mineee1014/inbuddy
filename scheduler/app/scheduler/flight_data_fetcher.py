import os

import pandas as pd
import requests

from app.logger.logger import log
from app.redis.redis import redis
from datetime import datetime
from bs4 import BeautifulSoup

DOMAIN = "https://www.airportal.go.kr/life/airinfo/RbHanList.jsp"

COLUMNS = ["날짜", "항공사", "편명", "출발지", "계획", "예상", "도착", "구분", "현황", "사유"]

PREFIX = "ddrivetip('"
SUFFIX = "에 의한"


def _request(date, dep_arr):
    def _extract(row):
        row_data = [date]
        for i in range(0, len(row), 2):
            string = str(row[i])
            c = BeautifulSoup(string, 'html.parser')
            text = c.text.strip()
            row_data.append(text)

            if i == 14:
                success = '출발' if dep_arr == 'D' else '도착'
                row_data.append(
                        string[string.find(PREFIX) + len(PREFIX):string.find(
                                SUFFIX)] if text != success else '')

        map(lambda x: x.encode('cp949', 'ignore').decode('cp949'), row_data)
        return row_data

    cat = pd.DataFrame(columns=COLUMNS)

    params = {
        "gubun": "c_getList",
        "depArr": dep_arr,
        "current_date": date,
        "airport": "RKSI",
        "al_icao": "",
        "fp_id": ""
    }

    url = DOMAIN + '?' + '&'.join(
            [f"{key}={value}" for key, value in params.items()])

    # request
    response = requests.get(url)

    soup = BeautifulSoup(response.text, 'html.parser')

    indent_one = soup.select("FORM > table > tr > TD > table > tr > td")
    indent_two = soup.select("FORM > table > tr > TD > table > td")
    tds = soup.select("FORM > table > td")

    # append rows
    loc = len(cat)
    cat.loc[loc] = _extract(indent_one)
    cat.loc[loc].apply(lambda row: row.encode("cp949").decode("cp949"))
    loc += 1
    cat.loc[loc] = _extract(indent_two)
    cat.loc[loc].apply(lambda row: row.encode("cp949").decode("cp949"))
    loc += 1
    for index in range(0, len(tds), 15):
        cat.loc[loc] = _extract(tds[index:index + 15])
        cat.loc[loc].apply(lambda row: row.encode("cp949").decode("cp949"))
        loc += 1

    cat = cat.reset_index(drop=True)
    return cat.to_json(orient="records", force_ascii=False)


def fetch():
    date = datetime.today().strftime("%Y%m%d")

    response_departure = _request(date, 'D')
    # response_arrive = request(date, 'A')

    if response_departure is not None:
        redis.select(redis.FLIGHTS_API)
        redis.set(date + 'D', response_departure)
        log.info("Fetched Departure Flight Data")
    else:
        log.warning("Failed to Fetch Departure Flight Data")