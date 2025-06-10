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
app = Flask(__name__) # BURADA __name__ OLDUĞUNDAN EMİN OLUN! İKİ ALTI ÇİZGİ
# Tüm rotalar için CORS'u etkinleştirme (frontend'in backend'e erişebilmesi için gerekli)
CORS(app)

# CoinGecko API temel URL'i
# Not: CoinGecko'nun ücretsiz planında API hız limiti bulunmaktadır.
# Sık isteklerde hata alabilirsiniz.
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
            return cached_data

    try:
        response = requests.get(url, timeout=10) # 10 saniye zaman aşımı
        response.raise_for_status() # HTTP hataları için hata fırlat
        data = response.json()
        
        # CoinGecko API'den hata döndüğünde
        if isinstance(data, dict) and "error" in data:
            print(f"API Yanıtı Hatası: {data['error']}")
            return {"error": data["error"]}
        
        if cache_key:
            CACHE[cache_key] = (data, time.time())
        return data
    
    except requests.exceptions.RequestException as e:
        print(f"API'ye bağlanırken hata oluştu: {e}")
        return {"error": f"API'ye bağlanırken hata oluştu: {e}"}
    except json.JSONDecodeError as e:
        print(f"API yanıtı JSON olarak ayrıştırılamadı: {e}")
        return {"error": f"API yanıtı işlenemedi: {e}"}
    except Exception as e:
        print(f"fetch_data_from_api'de beklenmeyen hata: {e}")
        return {"error": f"Beklenmeyen hata: {e}"}


def create_chart_image(dates, values, title, y_label, color):
    """
    Matplotlib kullanarak çizgi grafik oluşturur ve Base64 string olarak döndürür.
    """
    plt.style.use('dark_background') # Koyu tema
    plt.figure(figsize=(10, 6))
    plt.plot(dates, values, color=color, linewidth=2)
    plt.title(title, color='white', fontsize=16)
    plt.xlabel('Tarih', color='white', fontsize=12)
    plt.ylabel(y_label, color='white', fontsize=12)
    plt.xticks(rotation=45, ha='right', color='lightgray')
    plt.yticks(color='lightgray')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()

    # Grafiği bir tampona kaydet
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', transparent=True)
    buffer.seek(0)
    plt.close() # Grafiği kapat

    # Base64 string'e dönüştür
    graphic_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return graphic_base64

# --- API Uç Noktaları (Rotlar) ---

@app.route('/')
def home():
    coin_id = "bitcoin" # Varsayılan olarak Bitcoin'i gösterelim
    url = f"{COINGECKO_BASE_URL}/coins/{coin_id}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=true"
    cache_key = f"coin_details_{coin_id}_home" # Cache key'i daha spesifik yapalım
    
    try:
        data = fetch_data_from_api(url, cache_key)
        
        # API'den veri çekilirken hata oluştuysa veya "error" anahtarı varsa
        if "error" in data or not data:
            print(f"API Hatası (home rotası): {data.get('error', 'API yanıtı boş veya hatalı.')}")
            # Hata durumunda boş veya varsayılan bir coin objesi gönder
            # index.html'in beklentilerini karşılayacak bir yapı olmalı
            return render_template('index.html', coin={
                "name": "Veri Yok", 
                "symbol": "N/A", 
                "image": {"small": "/static/placeholder.png"}, # Varsayılan bir resim path'i
                "market_data": {
                    "current_price": {"usd": "N/A"}, 
                    "market_cap_rank": "N/A", 
                    "market_cap": {"usd": "N/A"},
                    "sparkline_7d": {"price": []} # Grafiğin hata vermemesi için boş liste
                }
            })

        # Sparkline verisinin varlığını kontrol et (grafik için kritik)
        if not data.get('market_data', {}).get('sparkline_7d', {}).get('price'):
            print(f"Sparkline verisi eksik: {coin_id}")
            # Eğer sparkline verisi eksikse, boş bir liste ile gönder
            data['market_data']['sparkline_7d'] = {"price": []}
        
        # Başarılı veri çekme durumunda
        return render_template('index.html', coin=data)

    except requests.exceptions.RequestException as req_e:
        print(f"Ağ Hatası (home rotası): {req_e}")
        return render_template('index.html', coin={
            "name": "Bağlantı Hatası", 
            "symbol": "NET", 
            "image": {"small": "/static/error.png"},
            "market_data": {
                "current_price": {"usd": "N/A"}, 
                "market_cap_rank": "N/A", 
                "market_cap": {"usd": "N/A"},
                "sparkline_7d": {"price": []}
            }
        })
    except Exception as e:
        print(f"Genel Hata (home rotası): {e}")
        return render_template('index.html', coin={
            "name": "Sunucu Hatası", 
            "symbol": "SRV", 
            "image": {"small": "/static/error.png"},
            "market_data": {
                "current_price": {"usd": "N/A"}, 
                "market_cap_rank": "N/A", 
                "market_cap": {"usd": "N/A"},
                "sparkline_7d": {"price": []}
            }
        })


@app.route('/global_market_data')
def get_global_market_data():
    url = f"{COINGECKO_BASE_URL}/global"
    cache_key = "global_market_data"
    data = fetch_data_from_api(url, cache_key)
    if "error" in data:
        return jsonify(data), 500
    return jsonify(data)

@app.route('/top_coins')
def get_top_coins():
    url = f"{COINGECKO_BASE_URL}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1&sparkline=false"
    cache_key = "top_coins"
    data = fetch_data_from_api(url, cache_key)
    if "error" in data:
        return jsonify(data), 500
    return jsonify(data)

@app.route('/trending_coins')
def get_trending_coins():
    url = f"{COINGECKO_BASE_URL}/search/trending"
    cache_key = "trending_coins"
    data = fetch_data_from_api(url, cache_key)
    if "error" in data:
        return jsonify(data), 500
    return jsonify(data)

@app.route('/coin_details/<coin_id>')
def get_coin_details(coin_id):
    url = f"{COINGECKO_BASE_URL}/coins/{coin_id}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=true"
    cache_key = f"coin_details_{coin_id}"
    data = fetch_data_from_api(url, cache_key)
    if "error" in data:
        return jsonify(data), 500
    return jsonify(data)


@app.route('/coin_price_chart/<coin_id>/<days>')
def get_coin_price_chart(coin_id, days):
    try:
        url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart?vs_currency=usd&days={days}&interval=daily"
        cache_key = f"price_chart_{coin_id}_{days}"
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
        color = '#00d8ff' # Mavi tonu

        graphic_base64 = create_chart_image(dates, values, title, y_label, color)
        
        return jsonify({"chart": graphic_base64})
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Fiyat grafiği oluşturma hatası ({coin_id}, {days} gün): {e}")
        return jsonify({"error": "Fiyat grafiği oluşturulurken bir hata oluştu."}), 500

@app.route('/coin_market_cap_chart/<coin_id>/<days>')
def get_coin_market_cap_chart(coin_id, days):
    try:
        url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart?vs_currency=usd&days={days}&interval=daily"
        cache_key = f"market_cap_chart_{coin_id}_{days}"
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
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Piyasa değeri grafiği oluşturma hatası ({coin_id}, {days} gün): {e}")
        return jsonify({"error": "Piyasa değeri grafiği oluşturulurken bir hata oluştu."}), 500


# Uygulama başlatma
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)