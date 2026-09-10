[app]
title = Estacionamiento Union
package.name = estacionamientounion
package.domain = com.tuempresa

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0
# charset_normalizer se fija a una versión vieja a propósito: desde la 3.0
# dejó de ser puro Python (agregó partes compiladas) y python-for-android
# no tiene receta para compilarlo, así que intenta bajar un wheel
# precompilado que no coincide con la versión de Python del build y truena.
# La 2.1.1 es pura Python y evita el problema por completo.
requirements = python3,kivy==2.3.1,pyjnius,urllib3==1.26.18,idna,certifi,charset-normalizer==2.1.1,requests==2.28.2,pillow

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

# Evita que Android mate la app mientras la cámara está abierta en primer plano.
android.wakelock = False

[buildozer]
log_level = 2
warn_on_root = 1
