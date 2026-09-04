import requests

weather = requests.get("https://wttr.in/Chennai?format=3")
print("Weather:", weather.text)

news = requests.get("http://feeds.bbci.co.uk/news/rss.xml")
print("News working:", "200" in str(news.status_code))