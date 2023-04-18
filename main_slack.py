import datetime
import os

import arxiv
import openai
from functions_framework import cloud_event
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# OpenAIのapiキー
openai.api_key = os.environ.get("OPENAI_API_KEY")
# Slack APIトークン
SLACK_API_TOKEN = os.environ.get("SLACK_API_TOKEN")

# Slackに投稿するチャンネル名を指定する
SLACK_CHANNEL = "#arxiv-ag"

CATEGORY = "math.AG"
ONE_DAY_DELTA = datetime.timedelta(days=1)


def get_summary(result: arxiv.Result):
    system = """与えられた論文の要点を3点のみでまとめ、以下のフォーマットで日本語で出力してください。```
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
    message = f"発行日: {date_str}\n{result.entry_id}\n{title_en}\n{title}\n{body}\n"

    return message


@cloud_event
def main(event):
    # Slack APIクライアントを初期化する
    client = WebClient(token=SLACK_API_TOKEN)
    # queryを用意
    end_time = datetime.datetime.now()
    start_time = end_time - ONE_DAY_DELTA
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

    # 論文情報をSlackに投稿する
    for i, result in enumerate(result_list):
        try:
            # Slackに投稿するメッセージを組み立てる
            message = "今日の論文です！ " + str(i + 1) + "本目\n" + get_summary(result)
            # Slackにメッセージを投稿する
            response = client.chat_postMessage(channel=SLACK_CHANNEL, text=message)
            print(f"Message posted: {response['ts']}")
        except SlackApiError as e:
            print(f"Error posting message: {e}")
