import requests
from configparser import ConfigParser

config = ConfigParser()
config.read("config.txt")
WEBHOOK_URL = config.get("WECHAT", "WEBHOOK_URL")


# 定义一个WeComBot的类，可以直接初始化，并且具备普通文本以及markdown文本的发送能力。
class WeComBot:
    def __init__(self):
        self.webhook_url = WEBHOOK_URL
        self.headers = {'Content-Type': 'application/json'}

    def send_text_message(self, content):
        data = {
            "msgtype": "text",
            "text": {
                "content": content
            }
        }

        try:
            response = requests.post(self.webhook_url, json=data, headers=self.headers)
            response.raise_for_status()
            print("Text message sent successfully!")
        except requests.exceptions.RequestException as e:
            print(f"Failed to send the text message: {e}")

    def send_markdown_message(self, content):
        headers = {'Content-Type': 'application/json'}
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }
        try:
            response = requests.post(self.webhook_url, json=data, headers=self.headers)
            response.raise_for_status()
            print("Message sent successfully!")
        except requests.exceptions.RequestException as e:
            print(f"Failed to send the message: {e}")
