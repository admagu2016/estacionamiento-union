import os
import re
import time
import sqlite3
import threading
import traceback
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup

try:
    import requests
    REQUESTS_DISPONIBLE = True
except ImportError:
    REQUESTS_DISPONIBLE = False

try:
    from PIL import Image as PILImage
    PIL_DISPONIBLE = True
except ImportError:
    PIL_DISPONIBLE = False

try:
    from jnius import autoclass
    from android import activity
    ANDROID_DISPONIBLE = True
except Exception:
    ANDROID_DISPONIBLE = False

REQUEST_TOMAR_FOTO = 100
REQUEST_ELEGIR_GALERIA = 200

MODELOS_COMUNES = ["Nissan", "Toyota", "Honda", "Volkswagen", "Chevrolet", "Ford", "Kia", "Hyundai", "Mazda", "BMW", "Audi", "Otro"]
COLORES_COMUNES = ["Blanco", "Negro", "Gris", "Plata", "Rojo", "Azul", "Verde", "Cafe", "Otro"]

# ==================== RUTAS ====================

def obtener_base_dir():
    if ANDROID_DISPONIBLE:
        try:
            from android.storage import app_storage_path
            ruta = app_storage_path()
            if ruta:
                return ruta
        except Exception as e:
            print(f"app_storage_path no disponible: {e}")
        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            ext_dir = PythonActivity.mActivity.getExternalFilesDir(None)
            if ext_dir:
                return ext_dir.getAbsolutePath()
        except Exception as e:
            print(f"getExternalFilesDir no disponible: {e}")
    base = os.getcwd()
    if not base or base == '/':
        base = os.path.dirname(os.path.abspath(__file__))
    return base

BASE_DIR = obtener_base_dir()
DB_NAME = os.path.join(BASE_DIR, "estacionamiento.db")
CARPETA_FOTOS = os.path.join(BASE_DIR, "fotos_placas")
print(f"Ruta de trabajo: {BASE_DIR}")

# ==================== CAPTURA DE FOTO (ANDROID) ====================

def crear_uri_mediastore(nombre_archivo):
    """
    Crea una entrada nueva en la galería del sistema (MediaStore) y devuelve
    su Uri. Pasar este Uri como EXTRA_OUTPUT a la cámara evita tener que
    declarar un FileProvider propio en el manifiesto (que Buildozer no
    soporta agregar de forma nativa).
    """
    ContentValues = autoclass('android.content.ContentValues')
    MediaStoreImagesMedia = autoclass('android.provider.MediaStore$Images$Media')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')

    resolver = PythonActivity.mActivity.getContentResolver()
    values = ContentValues()
    values.put(MediaStoreImagesMedia.DISPLAY_NAME, nombre_archivo)
    values.put(MediaStoreImagesMedia.MIME_TYPE, "image/jpeg")
    return resolver.insert(MediaStoreImagesMedia.EXTERNAL_CONTENT_URI, values)

def copiar_uri_a_archivo(uri, destino_path):
    """Copia el contenido de un content:// Uri de Android a un archivo local."""
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    FileOutputStream = autoclass('java.io.FileOutputStream')

    resolver = PythonActivity.mActivity.getContentResolver()
    input_stream = resolver.openInputStream(uri)
    output_stream = FileOutputStream(destino_path)
    try:
        buf = bytearray(8192)
        n = input_stream.read(buf)
        while n != -1:
            output_stream.write(buf, 0, n)
            n = input_stream.read(buf)
    finally:
        input_stream.close()
        output_stream.close()

# ==================== OCR ====================

def extraer_placa_super_permisivo(texto_crudo):
    """NUNCA devuelve vacío si hay texto. Limpia y devuelve la secuencia alfanumérica."""
    if not texto_crudo:
        return ""

    texto = texto_crudo.upper()
    texto_limpio = re.sub(r'[^A-Z0-9-]', '', texto)

    if len(texto_limpio) >= 3:
        if '-' in texto_limpio:
            partes = texto_limpio.split('-')
            return '-'.join(partes[:3])
        return texto_limpio[:10]

    return texto_limpio

def comprimir_imagen_para_ocr(ruta_imagen, max_bytes=900 * 1024, max_dimension=1600):
    """La key gratuita de OCR.space ('helloworld') rechaza imágenes de más de 1MB."""
    if not PIL_DISPONIBLE:
        print("Pillow no disponible, no se puede comprimir la imagen.")
        return ruta_imagen

    try:
        img = PILImage.open(ruta_imagen)
        img = img.convert("RGB")

        if max(img.size) > max_dimension:
            ratio = max_dimension / float(max(img.size))
            nuevo_tamano = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(nuevo_tamano, PILImage.LANCZOS)

        if not os.path.exists(CARPETA_FOTOS):
            os.makedirs(CARPETA_FOTOS, exist_ok=True)

        destino = os.path.join(CARPETA_FOTOS, "temp_ocr.jpg")
        calidad = 85
        img.save(destino, "JPEG", quality=calidad)

        while os.path.getsize(destino) > max_bytes and calidad > 25:
            calidad -= 10
            img.save(destino, "JPEG", quality=calidad)

        return destino
    except Exception as e:
        print(f"Error comprimiendo imagen: {e}")
        return ruta_imagen

def consultar_ocr_space(ruta_imagen):
    if not REQUESTS_DISPONIBLE:
        print("Librería requests no disponible")
        return ""
    if not ruta_imagen or not os.path.isfile(ruta_imagen):
        print("ERROR: Ruta no válida")
        return ""

    ruta_a_enviar = comprimir_imagen_para_ocr(ruta_imagen)

    try:
        url = "https://api.ocr.space/parse/image"
        with open(ruta_a_enviar, 'rb') as f:
            response = requests.post(
                url,
                files={'file': f},
                data={'apikey': 'helloworld', 'language': 'eng', 'OCREngine': '2'},
                timeout=30
            )

        if response.status_code == 200:
            res = response.json()
            if res.get('IsErroredOnProcessing'):
                print(f"ERROR API: {res.get('ErrorMessage', 'Desconocido')}")
                return ""
            if res.get('ParsedResults'):
                texto = res['ParsedResults'][0]['ParsedText']
                return extraer_placa_super_permisivo(texto)
            print(f"ERROR API: {res.get('ErrorMessage', 'Desconocido')}")
        else:
            print(f"ERROR HTTP {response.status_code}: {response.text[:300]}")

        return ""
    except Exception as e:
        print(f"ERROR OCR: {e}")
        return ""

# ==================== BASE DE DATOS ====================

def inicializar_bd():
    try:
        if not os.path.exists(CARPETA_FOTOS):
            os.makedirs(CARPETA_FOTOS, exist_ok=True)

        with sqlite3.connect(DB_NAME) as conexion:
            cursor = conexion.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vehiculos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    placa TEXT NOT NULL,
                    marca_modelo TEXT,
                    color TEXT,
                    hora_entrada TEXT NOT NULL,
                    hora_salida TEXT,
                    tipo_tarifa TEXT,
                    total REAL,
                    estado TEXT NOT NULL,
                    foto_path TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS turnos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inicio_turno TEXT NOT NULL,
                    fin_turno TEXT,
                    total_vendido REAL DEFAULT 0.0,
                    estado TEXT DEFAULT 'abierto'
                )
            """)
            conexion.commit()

            cursor.execute("SELECT id FROM turnos WHERE estado = 'abierto'")
            if not cursor.fetchone():
                inicio_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO turnos (inicio_turno, estado) VALUES (?, 'abierto')", (inicio_actual,))
                conexion.commit()
        return True
    except Exception as e:
        print(f"Error detallado BD: {e}")
        return False

def obtener_turno_actual():
    with sqlite3.connect(DB_NAME) as conexion:
        cursor = conexion.cursor()
        cursor.execute("SELECT id, inicio_turno FROM turnos WHERE estado = 'abierto' ORDER BY id DESC LIMIT 1")
        return cursor.fetchone()

def calcular_tarifa_tabla(minutos_totales, tipo_tarifa):
    if tipo_tarifa == "fija_50":
        return 50.0
    horas = minutos_totales / 60.0
    if horas <= 1.0: return 25.0
    elif horas <= 2.0: return 50.0
    elif horas <= 3.0: return 75.0
    elif horas <= 4.0: return 100.0
    elif horas <= 5.0: return 125.0
    elif horas <= 6.0: return 150.0
    elif horas <= 7.0: return 175.0
    elif horas <= 8.0: return 200.0
    elif horas <= 9.0: return 225.0
    elif horas <= 10.0: return 250.0
    elif horas <= 11.0: return 275.0
    elif horas <= 12.0: return 300.0
    else: return 350.0

def registrar_entrada(placa, marca_modelo, color, tipo_tarifa_seleccionada, foto_path):
    try:
        with sqlite3.connect(DB_NAME) as conexion:
            cursor = conexion.cursor()
            cursor.execute("SELECT id FROM vehiculos WHERE placa = ? AND estado = 'activo'", (placa,))
            if cursor.fetchone():
                return False, "La placa ya se encuentra activa."

            ahora = datetime.now()
            hora_str = ahora.strftime("%Y-%m-%d %H:%M:%S")
            hora_actual_num = ahora.hour + ahora.minute / 60.0

            tarifa_final = tipo_tarifa_seleccionada if (7.0 <= hora_actual_num <= 16.0) else "por_hora"

            cursor.execute("""
                INSERT INTO vehiculos (placa, marca_modelo, color, hora_entrada, tipo_tarifa, estado, foto_path)
                VALUES (?, ?, ?, ?, ?, 'activo', ?)
            """, (placa, marca_modelo, color, hora_str, tarifa_final, foto_path))
            conexion.commit()
        return True, "Vehículo registrado correctamente."
    except Exception as e:
        return False, f"Error: {str(e)}"

def registrar_salida(vehiculo_id):
    try:
        with sqlite3.connect(DB_NAME) as conexion:
            cursor = conexion.cursor()
            cursor.execute("SELECT placa, marca_modelo, color, hora_entrada, tipo_tarifa FROM vehiculos WHERE id = ?", (vehiculo_id,))
            resultado = cursor.fetchone()

            if not resultado:
                return False, 0.0, "Vehículo no encontrado."

            placa, marca_modelo, color, hora_entrada_str, tipo_tarifa = resultado
            hora_entrada = datetime.strptime(hora_entrada_str, "%Y-%m-%d %H:%M:%S")
            hora_salida = datetime.now()

            minutos_totales = (hora_salida - hora_entrada).total_seconds() / 60.0
            total = calcular_tarifa_tabla(minutos_totales, tipo_tarifa)

            cursor.execute("""
                UPDATE vehiculos
                SET hora_salida = ?, total = ?, estado = 'salido'
                WHERE id = ?
            """, (hora_salida.strftime("%Y-%m-%d %H:%M:%S"), total, vehiculo_id))
            conexion.commit()

        return True, total, f"Auto: {marca_modelo} ({color})\nPlaca: {placa}\nTiempo: {int(minutos_totales)} min\nTOTAL: ${total:.2f}"
    except Exception as e:
        return False, 0.0, f"Error: {str(e)}"

def obtener_activos():
    try:
        with sqlite3.connect(DB_NAME) as conexion:
            cursor = conexion.cursor()
            cursor.execute("SELECT id, placa, marca_modelo, color, hora_entrada, foto_path FROM vehiculos WHERE estado = 'activo' ORDER BY id DESC")
            return cursor.fetchall()
    except Exception as e:
        print(f"Error obteniendo activos: {e}")
        return []

# ==================== INTERFAZ ====================

class FilaVehiculo(BoxLayout):
    def __init__(self, vehiculo, on_foto, on_cobrar, **kwargs):
        super().__init__(orientation='horizontal', size_hint_y=None, height=dp(56), spacing=dp(6), **kwargs)
        vid, placa, modelo, color, hora_entrada, foto_path = vehiculo
        hora_corta = hora_entrada[11:16] if len(hora_entrada) >= 16 else hora_entrada

        info = Label(
            text=f"[b]{placa}[/b]\n{modelo} ({color}) - {hora_corta}",
            markup=True, halign='left', valign='middle', font_size='12sp'
        )
        info.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        self.add_widget(info)

        btn_foto = Button(text="Foto", size_hint_x=None, width=dp(64))
        btn_foto.bind(on_release=lambda *_: on_foto(foto_path))
        self.add_widget(btn_foto)

        btn_cobrar = Button(text="Cobrar", size_hint_x=None, width=dp(80), background_color=(0.83, 0.22, 0.21, 1))
        btn_cobrar.bind(on_release=lambda *_: on_cobrar(vid))
        self.add_widget(btn_cobrar)


class EstacionamientoApp(App):
    def build(self):
        self.title = "Estacionamiento Unión"
        self.foto_temporal_path = ""
        self.uri_captura_actual = None

        if not inicializar_bd():
            Clock.schedule_once(lambda dt: self._mostrar_popup("Error", "No se pudo inicializar la base de datos."))

        root = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(6))

        turno = obtener_turno_actual()
        texto_turno = f"Turno iniciado: {turno[1]}" if turno else "Turno: -"
        self.lbl_turno = Label(text=texto_turno, size_hint_y=None, height=dp(22), font_size='12sp')
        root.add_widget(self.lbl_turno)

        panel_registro = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(320), spacing=dp(4))

        btn_foto = Button(text="Tomar Foto y Detectar Placa", size_hint_y=None, height=dp(44),
                           background_color=(0, 0.6, 0.55, 1))
        btn_foto.bind(on_release=lambda *_: self.tomar_foto())
        panel_registro.add_widget(btn_foto)

        self.lbl_estado_foto = Label(text="[Sin foto cargada]", size_hint_y=None, height=dp(20),
                                      color=(0.8, 0.2, 0.2, 1), font_size='11sp')
        panel_registro.add_widget(self.lbl_estado_foto)

        btn_galeria = Button(text="No se detectó -- Elegir de galería", size_hint_y=None, height=dp(28), font_size='10sp')
        btn_galeria.bind(on_release=lambda *_: self.elegir_de_galeria())
        panel_registro.add_widget(btn_galeria)

        fila_placa = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(4))
        fila_placa.add_widget(Label(text="Placa:", size_hint_x=0.3))
        self.entry_placa = TextInput(multiline=False)
        fila_placa.add_widget(self.entry_placa)
        panel_registro.add_widget(fila_placa)

        fila_modelo = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(4))
        fila_modelo.add_widget(Label(text="Modelo:", size_hint_x=0.3))
        self.spinner_modelo = Spinner(text="Seleccionar", values=MODELOS_COMUNES)
        fila_modelo.add_widget(self.spinner_modelo)
        panel_registro.add_widget(fila_modelo)

        fila_color = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(4))
        fila_color.add_widget(Label(text="Color:", size_hint_x=0.3))
        self.spinner_color = Spinner(text="Seleccionar", values=COLORES_COMUNES)
        fila_color.add_widget(self.spinner_color)
        panel_registro.add_widget(fila_color)

        fila_tarifa = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(4))
        fila_tarifa.add_widget(Label(text="Tarifa:", size_hint_x=0.3))
        self.spinner_tarifa = Spinner(text="por_hora", values=["por_hora", "fija_50"])
        fila_tarifa.add_widget(self.spinner_tarifa)
        panel_registro.add_widget(fila_tarifa)

        btn_entrar = Button(text="Registrar Entrada", size_hint_y=None, height=dp(42),
                             background_color=(0.3, 0.7, 0.3, 1))
        btn_entrar.bind(on_release=lambda *_: self.accion_entrada())
        panel_registro.add_widget(btn_entrar)

        root.add_widget(panel_registro)

        root.add_widget(Label(text="Autos activos", size_hint_y=None, height=dp(24), bold=True))
        scroll = ScrollView()
        self.lista_activos = GridLayout(cols=1, size_hint_y=None, spacing=dp(4))
        self.lista_activos.bind(minimum_height=self.lista_activos.setter('height'))
        scroll.add_widget(self.lista_activos)
        root.add_widget(scroll)

        if ANDROID_DISPONIBLE:
            activity.bind(on_activity_result=self.on_activity_result)

        self.refrescar_lista()
        return root

    # --- Ciclo de vida Android: sin esto la app puede morir al abrir la cámara ---
    def on_pause(self):
        return True

    def on_resume(self):
        pass

    # --- Utilidades UI ---
    def _mostrar_popup(self, titulo, mensaje):
        contenido = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        contenido.add_widget(Label(text=mensaje))
        popup = Popup(title=titulo, content=contenido, size_hint=(0.85, 0.4))
        btn_cerrar = Button(text="OK", size_hint_y=None, height=dp(40))
        btn_cerrar.bind(on_release=lambda *_: popup.dismiss())
        contenido.add_widget(btn_cerrar)
        popup.open()

    # --- Captura de foto ---
    def tomar_foto(self):
        if not ANDROID_DISPONIBLE:
            self.lbl_estado_foto.text = "[Cámara no disponible en escritorio]"
            return
        try:
            nombre = f"placa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            uri = crear_uri_mediastore(nombre)
            if uri is None:
                self.lbl_estado_foto.text = "[No se pudo crear la foto en galería]"
                return
            self.uri_captura_actual = uri

            Intent = autoclass('android.content.Intent')
            MediaStore = autoclass('android.provider.MediaStore')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')

            intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            intent.putExtra(MediaStore.EXTRA_OUTPUT, uri)
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
            PythonActivity.mActivity.startActivityForResult(intent, REQUEST_TOMAR_FOTO)
            self.lbl_estado_foto.text = "[Abriendo cámara...]"
        except Exception as e:
            print(f"Error abriendo cámara: {e}")
            traceback.print_exc()
            self.lbl_estado_foto.text = "[Error abriendo cámara]"

    def elegir_de_galeria(self):
        if not ANDROID_DISPONIBLE:
            self.lbl_estado_foto.text = "[Selector no disponible en escritorio]"
            return
        try:
            Intent = autoclass('android.content.Intent')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            intent = Intent(Intent.ACTION_GET_CONTENT)
            intent.setType("image/*")
            PythonActivity.mActivity.startActivityForResult(intent, REQUEST_ELEGIR_GALERIA)
            self.lbl_estado_foto.text = "[Elige una imagen...]"
        except Exception as e:
            print(f"Error abriendo galería: {e}")
            self.lbl_estado_foto.text = "[Error abriendo galería]"

    def on_activity_result(self, request_code, result_code, intent):
        try:
            Activity = autoclass('android.app.Activity')
            resultado_ok = (result_code == Activity.RESULT_OK)
        except Exception:
            resultado_ok = False

        if not resultado_ok:
            Clock.schedule_once(lambda dt: setattr(self.lbl_estado_foto, 'text', "[Cancelado]"))
            return

        if request_code == REQUEST_TOMAR_FOTO:
            uri = self.uri_captura_actual
        elif request_code == REQUEST_ELEGIR_GALERIA:
            uri = intent.getData() if intent else None
        else:
            return

        if uri is None:
            Clock.schedule_once(lambda dt: setattr(self.lbl_estado_foto, 'text', "[No se obtuvo la foto]"))
            return

        Clock.schedule_once(lambda dt: setattr(self.lbl_estado_foto, 'text', "[Analizando foto...]"))
        threading.Thread(target=self._procesar_foto_hilo, args=(uri,), daemon=True).start()

    def _procesar_foto_hilo(self, uri):
        placa_detectada = ""
        try:
            if not os.path.exists(CARPETA_FOTOS):
                os.makedirs(CARPETA_FOTOS, exist_ok=True)
            destino = os.path.join(CARPETA_FOTOS, f"placa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
            copiar_uri_a_archivo(uri, destino)
            self.foto_temporal_path = destino
            placa_detectada = consultar_ocr_space(destino)
        except Exception as e:
            print(f"Error procesando foto: {e}")
            traceback.print_exc()
        Clock.schedule_once(lambda dt: self._aplicar_resultado_ocr(placa_detectada))

    def _aplicar_resultado_ocr(self, placa_detectada):
        if placa_detectada:
            self.entry_placa.text = placa_detectada
            self.lbl_estado_foto.text = f"[Placa: {placa_detectada}]"
        else:
            self.lbl_estado_foto.text = "[OCR sin texto, ingrésala manualmente]"

    # --- Registro / cobro ---
    def accion_entrada(self):
        placa = self.entry_placa.text.strip().upper()
        modelo = self.spinner_modelo.text
        color = self.spinner_color.text
        tarifa = self.spinner_tarifa.text
        foto = self.foto_temporal_path

        if not placa:
            self._mostrar_popup("Error", "Ingresa la placa.")
            return
        if modelo == "Seleccionar":
            self._mostrar_popup("Error", "Selecciona el modelo.")
            return
        if color == "Seleccionar":
            self._mostrar_popup("Error", "Selecciona el color.")
            return

        exito, mensaje = registrar_entrada(placa, modelo, color, tarifa, foto)
        if exito:
            self._mostrar_popup("Éxito", mensaje)
            self.entry_placa.text = ""
            self.spinner_modelo.text = "Seleccionar"
            self.spinner_color.text = "Seleccionar"
            self.foto_temporal_path = ""
            self.lbl_estado_foto.text = "[Sin foto cargada]"
            self.refrescar_lista()
        else:
            self._mostrar_popup("Aviso", mensaje)

    def cobrar_salida(self, vehiculo_id):
        exito, _total, mensaje = registrar_salida(vehiculo_id)
        if exito:
            self._mostrar_popup("Cobro", mensaje)
            self.refrescar_lista()
        else:
            self._mostrar_popup("Error", mensaje)

    def ver_foto(self, ruta):
        if not ruta or not os.path.exists(ruta):
            self._mostrar_popup("Sin foto", "Este vehículo no tiene foto asociada.")
            return
        if not ANDROID_DISPONIBLE:
            self._mostrar_popup("Foto", f"Guardada en:\n{ruta}")
            return
        try:
            Intent = autoclass('android.content.Intent')
            Uri = autoclass('android.net.Uri')
            File = autoclass('java.io.File')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')

            file_obj = File(os.path.abspath(ruta))
            uri = Uri.fromFile(file_obj)

            intent = Intent(Intent.ACTION_VIEW)
            intent.setDataAndType(uri, "image/*")
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            PythonActivity.mActivity.startActivity(intent)
        except Exception as e:
            # En algunas versiones de Android esto puede fallar por restricciones
            # de FileUriExposedException; de momento cae al respaldo de mostrar la ruta.
            print(f"Error mostrando foto: {e}")
            self._mostrar_popup("Foto", f"Guardada en:\n{ruta}")

    def refrescar_lista(self):
        self.lista_activos.clear_widgets()
        for fila in obtener_activos():
            row = FilaVehiculo(fila, on_foto=self.ver_foto, on_cobrar=self.cobrar_salida)
            self.lista_activos.add_widget(row)


if __name__ == "__main__":
    EstacionamientoApp().run()
