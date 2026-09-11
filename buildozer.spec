[app]
title = Estacionamiento Union
package.name = estacionamientounion
package.domain = com.tuempresa

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0
# Ya no se usa 'requests': la llamada a OCR.space se hace con urllib de la
# librería estándar (ver main.py) para evitar el conflicto de versiones de
# charset_normalizer que rompía la compilación en python-for-android.
requirements = python3,kivy==2.3.1,pyjnius,pillow

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
