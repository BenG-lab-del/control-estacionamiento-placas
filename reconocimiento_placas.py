import time
import cv2
import serial
import mysql.connector
from datetime import datetime
import easyocr

# Conexión al servidor local de Laragon
try:
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="estacionamiento"
    )
    cursor = db.cursor()
    print("Conexión a la base de datos exitosa.")
except Exception as e:
    print(f"Error al conectar con la base de datos: {e}")
    db = None

# Configura el puerto serie del Arduino
PUERTO_SERIAL = "COM4"
BAUD_RATE = 9600

try:
    arduino = serial.Serial(PUERTO_SERIAL, BAUD_RATE, timeout=1)
    time.sleep(2)
    print("Conexión serial establecida con éxito.")
except Exception as e:
    print(f"Error al conectar con el Arduino: {e}")
    arduino = None

# Inicializar el lector de OCR (idioma español/inglés)
print("Cargando modelo de IA para lectura de placas...")
# Si tienes tarjeta gráfica NVIDIA puedes poner gpu=True, si usas CPU déjalo en False
lector_ocr = easyocr.Reader(['es', 'en'], gpu=False)

# Placa autorizada que deseas reconocer
PLACA_AUTORIZADA = "ABC1234"  # Cambiala por la placa real que probarás

# Inicializar la cámara web
cap = cv2.VideoCapture(0)

print("Iniciando cámara... Presiona 'q' para salir.")
ultimo_envio_autorizado = 0
ultimo_envio_denegado = 0
contador_frames = 0  # Para optimizar y no procesar OCR en todos los cuadros seguidos

while True:
    ret, frame = cap.read()
    if not ret:
        print("No se pudo acceder a la cámara.")
        break

    contador_frames += 1
    placa_detectada_actual = None

    # Procesar OCR cada 5 frames para que el video no se trabe (optimización de rendimiento)
    if contador_frames % 5 == 0:
        # Reducir tamaño opcionalmente para agilizar
        frame_pequeno = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        
        # Leer textos en la imagen
        resultados = lector_ocr.readtext(frame_pequeno)
        
        for (bbox, texto, probabilidad) in resultados:
            # Limpiar el texto detectado (quitar espacios, guiones y pasar a mayúsculas)
            texto_limpio = ''.join(e for e in texto if e.isalnum()).upper()
            
            # Imprimir para depuración en pantalla qué va leyendo la cámara
            if probabilidad > 0.4:  # Umbral de confianza
                print(f"Texto detectado: {texto_limpio} (Confianza: {probabilidad:.2f})")
                
                # Si coincide con la placa autorizada
                if PLACA_AUTORIZADA in texto_limpio:
                    placa_detectada_actual = texto_limpio
                    break

    tiempo_actual = time.time()

    # --- CASO 1: PLACA AUTORIZADA ---
    if placa_detectada_actual:
        if tiempo_actual - ultimo_envio_autorizado > 7:
            print(f"¡Placa AUTORIZADA detectada: {placa_detectada_actual}! Abriendo pluma...")
            
            # Guardar en base de datos
            if db and db.is_connected():
                fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                try:
                    sql = "INSERT INTO accesos (nombre, fecha_hora) VALUES (%s, %s)"
                    valores = (f"Placa: {placa_detectada_actual}", fecha_actual)
                    cursor.execute(sql, valores)
                    db.commit()
                    print(f"✅ Acceso AUTORIZADO guardado en BD a las {fecha_actual}")
                except Exception as e:
                    print(f"Error al guardar en BD: {e}")

            # Activar Arduino (Servomotor a 90 grados por 7 segundos)
            if arduino:
                arduino.write(b"1")
                time.sleep(7)
                print("Cerrando pluma...")
                arduino.write(b'0')
            
            ultimo_envio_autorizado = tiempo_actual

    # Mostrar la ventana con el video en tiempo real
    cv2.imshow("Control de Estacionamiento - Placas", frame)

    # Salir con la tecla 'q'
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# Liberar recursos
cap.release()
cv2.destroyAllWindows()
if arduino:
    arduino.close()
if db and db.is_connected():
    cursor.close()
    db.close()
    print("Conexión a BD cerrada.")