import json
import requests
import hashlib
import os
import time

class ArticleProvider():
    def walker(self, source):
        domain = f"{source}.discord.com"
        page = 1
        articles = []

        os.makedirs(f"./{source}", exist_ok=True)

        while True:
            response = requests.get(
                f'https://{domain}/api/v2/help_center/en-us/articles.json?page={page}',
                timeout=5
            )

            if response.status_code != 200:
                break

            data = response.json()
            if not data.get('articles'):
                break
            
            for article in data['articles']:
                with open(f"./{source}/{article['id']}.md", "w", encoding="utf-8") as file:
                    file.write(article['body'])
                
                article['body'] = hashlib.sha256(article['body'].encode('utf-8')).hexdigest()
                articles.append(article)

            page += 1
            time.sleep(0.25)
        
        return {source: articles}