import json
import os
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

URL = "https://www.elcorteingles.es/electronica/reacondicionados/ordenadores-y-accesorios/ordenadores/brand::Apple/"
ARCHIVO_VISTOS = "vistos.json"

EMAIL_EMISOR = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASS")
EMAIL_RECEPTOR = os.environ.get("EMAIL_TO")

def obtener_productos():
    productos = {}
    with sync_playwright() as p:
        # Lanzamos un navegador Chromium limpio
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="es-ES",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        # ESTA LÍNEA SUSTITUYE A PLAYWRIGHT-STEALTH: Oculta a la web que somos un bot
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Añadimos el segundo actual a la URL para evitar cualquier caché del servidor de ECI
        url_fresca = f"{URL}?_={int(time.time())}"
        print(f"Accediendo a El Corte Inglés: {url_fresca}")

        try:
            response = page.goto(url_fresca, wait_until="domcontentloaded", timeout=45000)
            if response and response.status == 403:
                print("Bloqueo 403 detectado en esta pasada.")
                browser.close()
                return None

            # Esperamos unos segundos a que cargue el listado dinámico
            time.sleep(6)
            
            # Buscamos enlaces de productos dentro del listado
            enlaces = page.query_selector_all("a.js-product-link, a.event, a[href*='/electronica/A']")
            for enlace in enlaces:
                href = enlace.get_attribute("href") or ""
                titulo = enlace.get_attribute("title") or enlace.inner_text().strip()
                titulo = " ".join(titulo.split())
                
                # Filtramos para quedarnos solo con fichas de producto reales
                if "/electronica/A" in href and len(titulo) > 5:
                    link_limpio = href.split("?")[0]
                    if not link_limpio.startswith("http"):
                        link_limpio = "https://www.elcorteingles.es" + link_limpio
                    productos[link_limpio] = titulo
        except Exception as e:
            print(f"Error al cargar la página: {e}")
            browser.close()
            return None

        browser.close()
    
    print(f"Productos encontrados ahora mismo: {len(productos)}")
    return productos

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
        print("Error de conexión en esta pasada. Se reintentará en la siguiente.")
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
