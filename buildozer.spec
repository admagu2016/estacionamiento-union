[app]
title = Estacionamiento Union
package.name = estacionamientounion
package.domain = com.tuempresa

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0
# Ya no se usa 'requests' en nuestro código (ver main.py, usamos urllib de la
# librería estándar). Pero Kivy 2.3.1 SÍ declara 'requests' como dependencia
# obligatoria propia, y eso arrastra 'charset_normalizer' (dependencia de
# requests) a la última versión (3.5.1), cuyo wheel para Android está mal
# etiquetado: pasa el chequeo de compatibilidad de Buildozer pero falla al
# instalarse de verdad. Lo fijamos a 3.4.9, que NO publica wheel específico
# para Android (solo uno universal puro-Python), evitando el wheel roto.
requirements = python3,kivy==2.3.1,pyjnius,pillow,charset-normalizer==3.4.9

orientation = portrait
fullscreen = 0

# Permisos: cámara para el Intent de captura, internet para OCR.space.
# WRITE/READ_EXTERNAL_STORAGE se piden por compatibilidad con versiones
# anteriores a Android 10; en versiones nuevas no son estrictamente
# necesarios porque usamos MediaStore, pero no está de más declararlos.
android.permissions = CAMERA,INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

android.api = 34
android.minapi = 24
android.archs = arm64-v8a,armeabi-v7a
android.allow_backup = True

# Forzamos la rama master de python-for-android: la versión publicada por
# defecto tiene un bug conocido (venv de pip corrupto durante el build)
# que ya está corregido en master pero no en el último release.
# https://github.com/kivy/python-for-android/pull/3360
p4a.branch = master

# Evita que Android mate la app mientras la cámara está abierta en primer plano.
android.wakelock = False

[buildozer]
log_level = 2
warn_on_root = 1
