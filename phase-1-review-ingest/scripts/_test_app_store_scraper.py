from app_store_scraper import AppStore

app = AppStore(country="in", app_name="groww", app_id=1404871703)
app.review(how_many=100)
print("count", len(app.reviews))
if app.reviews:
    print("sample keys", app.reviews[0].keys())
    print("sample", app.reviews[0])
