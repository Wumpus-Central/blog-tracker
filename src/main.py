import json
import modules.providers.articles as articles_provider 
import modules.providers.blog as blog_provider

class ScraperEngine:
    def __init__(self):
        self.state_file = "data/state.json"
        self.new_data = {}
        self.old_data = {}

    def run(self):
        print("🚀 Starting Scraping Engine...")
        # TODO state_load
        # TODO finish articles support
        articles = articles_provider.ArticleProvider()

        article_sources = [
            'support',
            'support-dev',
            'support-apps',
            'creator-support'
        ]

        for source in article_sources:
            self.new_data.update(articles.walker(source))

        # TODO blog_provider
        # TODO diff_logic

if __name__ == "__main__":
    engine = ScraperEngine()
    engine.run()
