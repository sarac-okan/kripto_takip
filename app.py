# Gerekli kütüphaneleri içe aktarma
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import requests
import matplotlib.pyplot as plt
import base64
from io import BytesIO
import datetime
import time # İstekler arasına gecikme koymak için
import json

# Flask uygulamasını başlatma
app = Flask(__name__)
# Tüm rotalar için CORS'u etkinleştirme (frontend'in backend'e erişebilmesi için gerekli)
CORS(app)

# CoinGecko API temel URL'i
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# Basit bir bellek içi önbellek (cache) mekanizması
# API hız limitlerini aşmamak ve performansı artırmak için kullanılır.
# Anahtar: API isteği URL'si, Değer: (Veri, Zaman damgası)
CACHE = {}
CACHE_EXPIRATION_TIME = 300 # Saniye cinsinden (5 dakika)

# --- Yardımcı Fonksiyonlar ---

def fetch_data_from_api(url, cache_key=None):
    """
    Belirtilen URL'den veri çeker ve basit bir önbellek kullanır.
    API hız limiti hatalarını da yakalamayı dener.
    """
    if cache_key and cache_key in CACHE:
        cached_data, timestamp = CACHE[cache_key]
        if (time.time() - timestamp) < CACHE_EXPIRATION_TIME:
            print(f"Önbellekten servis ediliyor: {cache_key}")
            return cached_data
    
    print(f"API'den çekiliyor: {url}")
    try:
        # CoinGecko API'nin hız limiti 100 istek/dakikadır.
        # Bu yüzden her istekten önce 1 saniye bekliyoruz.
        time.sleep(1) 
        response = requests.get(url)
        response.raise_for_status() # HTTP hataları için exception fırlatır (4xx veya 5xx)
        data = response.json()
        if cache_key:
            CACHE[cache_key] = (data, time.time())
        return data
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print("API Hız Limiti Aşıldı. Lütfen bir süre bekleyin.")
            return {"error": "API Hız Limiti Aşıldı. Lütfen bir süre sonra tekrar deneyin."}
        else:
            print(f"HTTP Hatası: {e.response.status_code} - {e.response.text}")
            raise ConnectionError(f"API isteği sırasında HTTP hatası oluştu: {e.response.status_code}")
    except requests.exceptions.ConnectionError as e:
        print(f"Bağlantı Hatası: {e}")
        raise ConnectionError("API'ye bağlanırken bir hata oluştu. İnternet bağlantınızı kontrol edin.")
    except Exception as e:
        print(f"Beklenmedik bir hata oluştu: {e}")
        raise Exception(f"Beklenmedik bir hata oluştu: {e}")

def create_chart_image(dates, values, title, y_label, color, show_grid=True):
    """
    Matplotlib kullanarak bir çizgi grafiği oluşturur ve Base64 kodlu PNG olarak döndürür.
    """
    plt.style.use('dark_background') # Koyu tema kullan
    fig, ax = plt.subplots(figsize=(10, 5)) # Grafik boyutu
    
    ax.plot(dates, values, color=color, linewidth=2) # Çizgi grafiği

    ax.set_title(title, color='#eee', fontsize=16) # Başlık rengi
    ax.set_ylabel(y_label, color='#eee', fontsize=12) # Y eksen etiketi rengi
    
    # X ekseni için tarih formatlayıcı
    fig.autofmt_xdate() # Tarih etiketlerini otomatik döndürme
    ax.tick_params(axis='x', colors='#eee') # X ekseni tik etiketleri rengi
    ax.tick_params(axis='y', colors='#eee') # Y ekseni tik etiketleri rengi

    # Izgara çizgileri
    if show_grid:
        ax.grid(True, linestyle='--', alpha=0.5, color='#333')
    
    # Arka plan rengini ayarla (figür ve eksen)
    fig.patch.set_facecolor('#1f1f1f') 
    ax.set_facecolor('#1f1f1f') 

    # Grafiği bir BytesIO nesnesine kaydet
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100) # dpi kalitesini ayarlar
    buf.seek(0)
    
    # Base64'e kodla
    graphic_base64 = base64.b64encode(buf.read()).decode('utf-8')
    
    plt.close(fig) # Bellek sızıntılarını önlemek için grafiği kapat
    return graphic_base64

# --- Flask Rotaları ---

@app.route('/')
def index():
    """
    Ana sayfayı render eder.
    """
    # Bu aslında ayrı bir HTML dosyası tarafından render edilir, ancak burada
    # genel bir karşılama metni veya yönlendirme yapılabilir.
    return "Welcome to Crypto Tracker Backend! Access API endpoints."

@app.route('/global_market_data')
def get_global_market_data():
    """
    Global piyasa verilerini döndürür.
    """
    url = f"{COINGECKO_BASE_URL}/global"
    cache_key = "global_data"
    try:
        data = fetch_data_from_api(url, cache_key)
        if "error" in data:
            return jsonify(data), 500
        # Sadece gerekli alanları döndür
        return jsonify({
            "total_market_cap_usd": data['data']['total_market_cap']['usd'],
            "total_volume_24h_usd": data['data']['total_volume']['usd']
        })
    except ConnectionError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Global piyasa verisi çekme hatası: {e}")
        return jsonify({"error": "Global piyasa verileri çekilirken bir hata oluştu."}), 500

@app.route('/trending_coins')
def get_trending_coins():
    """
    Trend olan kripto paraları döndürür.
    """
    url = f"{COINGECKO_BASE_URL}/search/trending"
    cache_key = "trending_coins"
    try:
        data = fetch_data_from_api(url, cache_key)
        if "error" in data:
            return jsonify(data), 500
        
        trending_coins = []
        for coin_data in data['coins']:
            coin = coin_data['item']
            trending_coins.append({
                "id": coin['id'],
                "name": coin['name'],
                "symbol": coin['symbol'],
                "market_cap_rank": coin.get('market_cap_rank', None),
                "large_image": coin.get('large', None)
            })
        return jsonify(trending_coins)
    except ConnectionError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Trend coin çekme hatası: {e}")
        return jsonify({"error": "Trend coinler çekilirken bir hata oluştu."}), 500

@app.route('/coin_details/<coin_id>')
def get_coin_details(coin_id):
    """
    Belirli bir kripto paranın detaylarını döndürür.
    """
    url = f"{COINGECKO_BASE_URL}/coins/{coin_id}"
    cache_key = f"coin_details_{coin_id}"
    try:
        data = fetch_data_from_api(url, cache_key)
        if "error" in data:
            return jsonify(data), 500
        
        # Sadece gerekli alanları döndür
        return jsonify({
            "id": data.get('id'),
            "symbol": data.get('symbol'),
            "name": data.get('name'),
            "description": data.get('description', {}).get('en', 'No description available.'),
            "image": {
                "thumb": data.get('image', {}).get('thumb'),
                "small": data.get('image', {}).get('small'),
                "large": data.get('image', {}).get('large')
            },
            "market_data": {
                "current_price": data.get('market_data', {}).get('current_price', {}),
                "market_cap": data.get('market_data', {}).get('market_cap', {}),
                "market_cap_rank": data.get('market_data', {}).get('market_cap_rank'),
                "sparkline_7d": data.get('market_data', {}).get('sparkline_7d')
            },
            "homepage": data.get('links', {}).get('homepage', [])[0] if data.get('links', {}).get('homepage') else None
        })
    except ConnectionError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Coin detayı çekme hatası ({coin_id}): {e}")
        return jsonify({"error": f"{coin_id} detayları çekilirken bir hata oluştu."}), 500


@app.route('/coin_chart/<coin_id>/<int:days>')
def get_coin_price_chart(coin_id, days):
    """
    Belirli bir kripto paranın geçmiş fiyat grafiğini döndürür.
    """
    if days not in [1, 7, 14, 30, 90, 180, 365, "max"]:
        return jsonify({"error": "Geçersiz gün sayısı. 1, 7, 14, 30, 90, 180, 365 veya 'max' olmalı."}), 400

    url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart?vs_currency=usd&days={days}&interval=daily"
    cache_key = f"price_chart_{coin_id}_{days}"
    try:
        market_data = fetch_data_from_api(url, cache_key)
        if "error" in market_data:
            return jsonify(market_data), 500
        
        prices = market_data.get('prices')
        
        if not prices:
            return jsonify({"error": f"No price data available for {coin_id} for the last {days} days."}), 404

        dates = [datetime.datetime.fromtimestamp(p[0] / 1000) for p in prices]
        values = [p[1] for p in prices]

        title = f'{coin_id.capitalize()} Fiyat Grafiği ({days} Gün)' if days != "max" else f'{coin_id.capitalize()} Fiyat Grafiği (Tüm Zamanlar)'
        y_label = 'Fiyat (USD)'
        color = '#00d8ff' # Turkuaz tonu

        graphic_base64 = create_chart_image(dates, values, title, y_label, color)
        
        return jsonify({"chart": graphic_base64})
    except ConnectionError as e:
        return jsonify({"error": str(e)}), 500
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Fiyat grafiği oluşturma hatası ({coin_id}, {days} gün): {e}")
        return jsonify({"error": "Fiyat grafiği oluşturulurken bir hata oluştu."}), 500

@app.route('/market_cap_chart/<coin_id>/<int:days>')
def get_coin_market_cap_chart(coin_id, days):
    """
    Belirli bir kripto paranın geçmiş piyasa değeri grafiğini döndürür.
    """
    if days not in [1, 7, 14, 30, 90, 180, 365, "max"]:
        return jsonify({"error": "Geçersiz gün sayısı. 1, 7, 14, 30, 90, 180, 365 veya 'max' olmalı."}), 400

    url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart?vs_currency=usd&days={days}&interval=daily"
    cache_key = f"market_cap_chart_{coin_id}_{days}"
    try:
        market_data = fetch_data_from_api(url, cache_key)
        if "error" in market_data:
            return jsonify(market_data), 500
        
        market_caps = market_data.get('market_caps')
        
        if not market_caps:
            return jsonify({"error": f"No market cap data available for {coin_id} for the last {days} days."}), 404

        dates = [datetime.datetime.fromtimestamp(p[0] / 1000) for p in market_caps]
        values = [p[1] for p in market_caps]

        title = f'{coin_id.capitalize()} Piyasa Değeri Grafiği ({days} Gün)' if days != "max" else f'{coin_id.capitalize()} Piyasa Değeri Grafiği (Tüm Zamanlar)'
        y_label = 'Piyasa Değeri (USD)'
        color = '#ff6b6b' # Kırmızı tonu

        graphic_base64 = create_chart_image(dates, values, title, y_label, color)
        
        return jsonify({"chart": graphic_base64})
    except ConnectionError as e:
        return jsonify({"error": str(e)}), 500
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Piyasa değeri grafiği oluşturma hatası ({coin_id}, {days} gün): {e}")
        return jsonify({"error": "Piyasa değeri grafiği oluşturulurken bir hata oluştu."}), 500


# Uygulama başlatma
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)