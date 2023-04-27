import datetime
import json
import os
from urllib.request import Request, urlopen

import arxiv
import openai
from functions_framework import cloud_event

# OpenAIのapiキー
openai.api_key = os.environ.get("OPENAI_API_KEY")
WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

CATEGORY = "math.AG"
ONE_DAY_DELTA = datetime.timedelta(days=1)


def post_discord(message: str) -> None:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "DiscordBot (private use) Python-urllib/3.10",
    }
    data = {"content": message}
    request = Request(
        WEBHOOK_URL,
        data=json.dumps(data).encode(),
        headers=headers,
    )

    with urlopen(request) as res:
        assert res.getcode() == 204


def get_summary(result: arxiv.Result):
    system = """あなたはプロの数学者です。与えられた数学論文の要点を3点のみでまとめ、以下のフォーマットで日本語で出力してください。```
    タイトルの日本語訳
    ・要点1
    ・要点2
    ・要点3
    ```"""

    text = f"title: {result.title}\nbody: {result.summary}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        temperature=0.25,
    )
    summary = response["choices"][0]["message"]["content"]
    title_en = result.title
    title, *body = summary.split("\n")
    body = "\n".join(body)
    date_str = result.published.strftime("%Y-%m-%d %H:%M:%S")
    message = f"投稿日時: {date_str}\n{result.entry_id}\n{title_en}\n{title}\n{body}\n\n"

    return message


@cloud_event
def main(event):
    # queryを用意
    end_time = datetime.datetime.now(datetime.timezone.utc)

    # 月曜は3日前、それ以外は1日前までの論文を取得する
    if end_time.weekday() == 0:
        start_time = datetime.datetime.combine(
            date=(end_time - ONE_DAY_DELTA * 4).date(), time=datetime.time(18, 0, 0)
        )
    else:
        start_time = datetime.datetime.combine(
            date=(end_time - ONE_DAY_DELTA * 2).date(), time=datetime.time(18, 0, 0)
        )
    print(f"{start_time} to {end_time}")
    start_time_str = start_time.strftime("%Y%m%d%H%M%S")
    end_time_str = end_time.strftime("%Y%m%d%H%M%S")
    query = f"cat:{CATEGORY} AND submittedDate:[{start_time_str} TO {end_time_str}]"

    # arxiv APIで最新の論文情報を取得する
    search = arxiv.Search(
        query=query,  # 検索クエリ
        sort_by=arxiv.SortCriterion.SubmittedDate,  # 論文を投稿された日付でソートする
        sort_order=arxiv.SortOrder.Ascending,  # 古い論文から順に取得する
    )
    # searchの結果をリストに格納
    result_list = []
    for result in search.results():
        print(result)
        result_list.append(result)

    # 論文情報をDiscordに投稿する
    for i, result in enumerate(result_list):
        try:
            # Discordに投稿するメッセージを組み立てる
            message = "今日の論文です！ " + str(i + 1) + "本目\n" + get_summary(result)
            # Discordにメッセージを投稿する
            post_discord(message=message)
        except Exception:
            print(f"error on {i+1}-th paper.")

    print("Done!")
