import json
import os
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

URL = "https://www.elcorteingles.es/electronica/reacondicionados/ordenadores-y-accesorios/ordenadores/brand::Apple/"
ARCHIVO_VISTOS = "vistos.json"

EMAIL_EMISOR = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASS")
EMAIL_RECEPTOR = os.environ.get("EMAIL_TO")

def obtener_productos():
    productos = {}
    with sync_playwright() as p:
        # Lanzamos un navegador Chromium real pero invisible
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
        stealth_sync(page) # Ocultamos que es un bot

        print("Accediendo a El Corte Inglés...")
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=45000)
            # Esperamos unos segundos a que carguen los productos dinámicos
            time.sleep(6)
            
            # Extraemos todos los enlaces que apuntan a productos de electrónica
            enlaces = page.query_selector_all("a[href*='/electronica/A']")
            for enlace in enlaces:
                href = enlace.get_attribute("href")
                titulo = enlace.get_attribute("title") or enlace.inner_text().strip()
                
                # Limpiamos saltos de línea y filtramos textos vacíos
                titulo = " ".join(titulo.split())
                if href and titulo and len(titulo) > 5:
                    link_limpio = href.split("?")[0]
                    if not link_limpio.startswith("http"):
                        link_limpio = "https://www.elcorteingles.es" + link_limpio
                    productos[link_limpio] = titulo
        except Exception as e:
            print(f"Error al cargar la página: {e}")
            browser.close()
            return None

        browser.close()
    
    print(f"Productos encontrados en esta pasada: {len(productos)}")
    return productos

def enviar_correo(nuevos):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_EMISOR
    msg["To"] = EMAIL_RECEPTOR
    msg["Subject"] = f"🍏 ¡{len(nuevos)} Nuevo(s) Mac Reacondicionado(s) en El Corte Inglés!"

    cuerpo = "Se han detectado nuevos ordenadores Apple reacondicionados:\n\n"
    for link, titulo in nuevos.items():
        cuerpo += f"• {titulo}\n  👉 {link}\n\n"

    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_EMISOR, EMAIL_PASSWORD)
        server.send_message(msg)
    print("¡Correo de alerta enviado con éxito!")

def main():
    productos_actuales = obtener_productos()
    if not productos_actuales:
        print("No se pudieron extraer productos (posible bloqueo temporal o sin stock). Se reintentará luego.")
        return

    if os.path.exists(ARCHIVO_VISTOS):
        with open(ARCHIVO_VISTOS, "r", encoding="utf-8") as f:
            vistos = json.load(f)
    else:
        vistos = {}

    # Comparamos los productos de la web con los que ya teníamos guardados
    nuevos = {k: v for k, v in productos_actuales.items() if k not in vistos}

    # Si hay productos nuevos y NO es la primera vez que ejecutamos el bot, enviamos correo
    if nuevos and vistos:
        print(f"¡Detectados {len(nuevos)} nuevos! Enviando email...")
        enviar_correo(nuevos)
    elif not vistos:
        print("Primera ejecución: guardando el catálogo actual como base sin enviar correo.")
    else:
        print("No hay productos nuevos.")

    # Guardamos la lista actualizada
    vistos.update(productos_actuales)
    with open(ARCHIVO_VISTOS, "w", encoding="utf-8") as f:
        json.dump(vistos, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
