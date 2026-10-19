import json
import os
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from curl_cffi import requests
from bs4 import BeautifulSoup

URL = "https://www.elcorteingles.es/electronica/reacondicionados/ordenadores-y-accesorios/ordenadores/brand::Apple/"
ARCHIVO_VISTOS = "vistos.json"

EMAIL_EMISOR = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASS")
EMAIL_RECEPTOR = os.environ.get("EMAIL_TO")

def obtener_productos():
    url_fresca = f"{URL}?_={int(time.time())}"
    print(f"Accediendo con camuflaje a: {url_fresca}")
    
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9",
        "Referer": "https://www.elcorteingles.es/",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        # Usamos una Sesión para guardar las cookies por si nos mandan un reto temporal (HTTP 202)
        with requests.Session(impersonate="safari15_5") as session:
            response = session.get(url_fresca, headers=headers, timeout=30)
            
            # Si nos mandan a la sala de espera, esperamos y reintentamos con la cookie ya guardada
            if response.status_code == 202:
                print("HTTP 202: Sala de espera de ECI detectada. Esperando 6 segundos y reintentando...")
                time.sleep(6)
                response = session.get(url_fresca, headers=headers, timeout=30)
            
            if response.status_code == 403:
                print("Bloqueo 403 detectado. Akamai ha bloqueado la IP.")
                return None
            elif response.status_code != 200:
                print(f"Error HTTP {response.status_code} al cargar la página.")
                print("Pista del error:", response.text[:150].replace('\n', ' '))
                return None

            soup = BeautifulSoup(response.text, "html.parser")
            productos = {}

            enlaces = soup.select("a.js-product-link, a.event, a[href*='/electronica/A']")
            for enlace in enlaces:
                href = enlace.get("href", "")
                titulo = enlace.get("title") or enlace.get_text(strip=True)
                titulo = " ".join(titulo.split())
                
                if "/electronica/A" in href and len(titulo) > 5:
                    link_limpio = href.split("?")[0]
                    if not link_limpio.startswith("http"):
                        link_limpio = "https://www.elcorteingles.es" + link_limpio
                    productos[link_limpio] = titulo

            print(f"Productos encontrados ahora mismo: {len(productos)}")
            return productos

    except Exception as e:
        print(f"Error de conexión en esta pasada: {e}")
        return None

def enviar_correo(nuevos):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_EMISOR
    msg["To"] = EMAIL_RECEPTOR
    msg["Subject"] = f"🍏 ¡{len(nuevos)} Nuevo(s) Mac Reacondicionado(s) en El Corte Inglés!"

    cuerpo = "¡Corre! Acaban de aparecer estos ordenadores Apple reacondicionados:\n\n"
    for link, titulo in nuevos.items():
        cuerpo += f"• {titulo}\n  👉 {link}\n\n"

    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_EMISOR, EMAIL_PASSWORD)
        server.send_message(msg)
    print("¡Correo de alerta enviado con éxito!")

def main():
    productos_actuales = obtener_productos()
    if productos_actuales is None:
        return

    if os.path.exists(ARCHIVO_VISTOS):
        with open(ARCHIVO_VISTOS, "r", encoding="utf-8") as f:
            vistos = json.load(f)
    else:
        vistos = {}

    nuevos = {k: v for k, v in productos_actuales.items() if k not in vistos}

    if nuevos:
        print(f"¡Detectados {len(nuevos)} nuevos! Enviando email...")
        enviar_correo(nuevos)
    else:
        print("Sigue sin haber novedades (0 nuevos).")

    vistos.update(productos_actuales)
    with open(ARCHIVO_VISTOS, "w", encoding="utf-8") as f:
        json.dump(vistos, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
