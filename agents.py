import requests
import pandas as pd
import json
from datetime import datetime
import time
from googleapiclient.discovery import build
from datetime import datetime, timezone
import isodate
import os

def load_config():
    """
    API anahtarlarını config.json dosyasından yükler
    Dosya yoksa varsayılan yapılandırmayı kullanır
    """
    config_file = 'config.json'
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            return json.load(f)
    else:
        # Varsayılan yapılandırma
        default_config = {
            "youtube": {
                "api_key": ""  # YouTube API anahtarınız
            },
            "search_api": {
                "api_key": ""  # SearchAPI.io anahtarı
            }
        }
        # Config dosyasını oluştur
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        print(f"\nLütfen {config_file} dosyasına API anahtarlarınızı ekleyin.")
        return default_config

# API Yapılandırmasını yükle
API_CONFIG = load_config()

# API anahtarlarını kontrol et
if not API_CONFIG['youtube']['api_key'] or not API_CONFIG['search_api']['api_key']:
    print("\nUYARI: API anahtarları eksik. Lütfen config.json dosyasını düzenleyin.")

def get_video_details(video_id, youtube):
    """
    YouTube API kullanarak video detaylarını alır
    """
    try:
        # Video detaylarını al
        video_response = youtube.videos().list(
            part='snippet,statistics,contentDetails',
            id=video_id
        ).execute()

        if not video_response['items']:
            return None

        video = video_response['items'][0]
        
        # Kanal detaylarını al
        channel_id = video['snippet']['channelId']
        channel_response = youtube.channels().list(
            part='statistics',
            id=channel_id
        ).execute()

        # ISO 8601 formatındaki süreyi dakikaya çevir
        duration = isodate.parse_duration(video['contentDetails']['duration'])
        duration_minutes = duration.total_seconds() / 60

        return {
            'duration': round(duration_minutes, 2),
            'like_numbers': int(video['statistics'].get('likeCount', 0)),
            'view_count': int(video['statistics'].get('viewCount', 0)),
            'comment_count': int(video['statistics'].get('commentCount', 0)),
            'subscribers_number': int(channel_response['items'][0]['statistics'].get('subscriberCount', 0)),
            'displayed_date': video['snippet']['publishedAt']
        }
    except Exception as e:
        print(f"Video detayları alınırken hata: {str(e)}")
        return None

def process_google_news(news_item):
    """
    Google News sonuçlarını işler ve standart formata dönüştürür
    """
    return {
        'position': news_item.get('position', ''),
        'title': news_item.get('title', ''),
        'link': news_item.get('link', ''),
        'source': news_item.get('source', ''),
        'date': news_item.get('date', ''),
        'snippet': news_item.get('snippet', ''),
        'favicon': news_item.get('favicon', ''),
        'thumbnail': news_item.get('thumbnail', '')
    }

def search_and_save_to_csv(query, engine="youtube", max_results=500):
    """
    Verilen sorgu ile arama yapar ve sonuçları CSV'ye kaydeder
    """
    youtube = None
    if engine == "youtube":
        try:
            youtube = build('youtube', 'v3', developerKey=API_CONFIG['youtube']['api_key'])
        except Exception as e:
            print(f"YouTube API yapılandırma hatası: {str(e)}")
            return False
    
    # SearchAPI.io için URL ve parametreler
    url = "https://www.searchapi.io/api/v1/search"
    params = {
        "engine": engine,
        "q": query,
        "api_key": API_CONFIG['search_api']['api_key'],
        "page": "1"
    }
    
    all_results = []
    page = 1
    max_pages = (max_results + 9) // 10
    
    while len(all_results) < max_results and page <= max_pages:
        current_params = params.copy()
        current_params["page"] = str(page)

        try:
            print(f"Sayfa {page} getiriliyor...", end='\r')
            response = requests.get(url, params=current_params)
            data = json.loads(response.text)
            
            if 'error' in data:
                print(f"\nAPI Hatası: {data['error']}")
                break

            if engine == "youtube":
                if 'videos' in data:
                    current_results = data['videos']
                    if not current_results:
                        break
                    
                    for video in current_results:
                        if len(all_results) >= max_results:
                            break
                            
                        video_id = None
                        if 'link' in video:
                            video_id = video['link'].split('v=')[-1].split('&')[0]
                        
                        video_info = {
                            'position': video.get('position', ''),
                            'title': video.get('title', ''),
                            'link': video.get('link', '')
                        }
                        
                        if video_id:
                            details = get_video_details(video_id, youtube)
                            if details:
                                video_info.update(details)
                            
                        all_results.append(video_info)

            elif engine == "google":
                if 'organic_results' in data:
                    current_results = data['organic_results']
                    for result in current_results:
                        if len(all_results) >= max_results:
                            break
                        result_info = {
                            'position': result.get('position', ''),
                            'title': result.get('title', ''),
                            'link': result.get('link', ''),
                            'snippet': result.get('snippet', ''),
                            'date': result.get('date', '')
                        }
                        all_results.append(result_info)
                else:
                    break

            elif engine == "google_news":
                if 'news_results' in data:
                    current_results = data['news_results']
                    for news in current_results:
                        if len(all_results) >= max_results:
                            break
                        news_info = process_google_news(news)
                        all_results.append(news_info)
                else:
                    break
            
            time.sleep(1)
            page += 1
            
        except Exception as e:
            print(f"\nHata oluştu: {str(e)}")
            break
    
    print("\n")
    
    if not all_results:
        print("Sonuç bulunamadı.")
        return False
    
    # DataFrame oluştur ve CSV'ye kaydet
    df = pd.DataFrame(all_results)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'search_results_{engine}_{timestamp}.csv'
    df.to_csv(filename, index=False, encoding='utf-8')
    print(f"Toplam {len(all_results)} sonuç {filename} dosyasına kaydedildi.")
    
    return True

def main():
    while True:
        print("\n=== Arama Motoru API ===")
        print("1. YouTube")
        print("2. Google")
        print("3. Google News")
        print("4. Çıkış")
        
        while True:
            try:
                engine_choice = input("\nArama motorunu seçin (1-4): ")
                if engine_choice in ['1', '2', '3', '4']:
                    break
                print("Lütfen geçerli bir seçim yapın!")
            except:
                print("Lütfen geçerli bir seçim yapın!")
        
        if engine_choice == '4':
            print("\nProgram sonlandırılıyor...")
            break
            
        engine_map = {
            '1': 'youtube',
            '2': 'google',
            '3': 'google_news'
        }
        
        engine = engine_map[engine_choice]
        
        query = input("\nArama sorgunuzu girin: ")
        
        while True:
            try:
                max_results = int(input("\nKaç sonuç istiyorsunuz? (1-500): "))
                if 1 <= max_results <= 500:
                    break
                print("Lütfen 1-500 arasında bir sayı girin!")
            except:
                print("Lütfen geçerli bir sayı girin!")
        
        print(f"\nArama yapılıyor...")
        print(f"Motor: {engine}")
        print(f"Sorgu: {query}")
        print(f"İstenen sonuç sayısı: {max_results}")
        
        success = search_and_save_to_csv(query, engine, max_results)
        
        if success:
            while True:
                continue_search = input("\nBaşka bir arama yapmak ister misiniz? (y/n): ").lower()
                if continue_search in ['y', 'n']:
                    break
                print("Lütfen 'y' veya 'n' girin!")
            
            if continue_search == 'n':
                print("\nProgram sonlandırılıyor...")
                break

if __name__ == "__main__":
    main()
