from pruebaDT import sms_alert
from datetime import date, time, datetime
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from hx711 import HX711

import os
import socket


from http.server import BaseHTTPRequestHandler, HTTPServer
import RPi.GPIO as GPIO
from time import*

# pines
trigger = 15
echo = 18
sck = 20
dt = 21


# manejo de datos pra la base de datos
def manejoDatos():
    try:
        ref = db.reference('embebidos')
        lista = list(ref.get()['Alarma'].split(','))
        dataB = {'Dias':[], 'Horas':[], 'Correo':[], 'Peso':[]}
        for i in range(len(lista)):
            sub = lista[i].strip('"[]').split('%')
            dataB['Dias'].append(sub[0])
            dataB['Horas'].append(sub[1])
            dataB['Correo'].append(sub[2])
            dataB['Peso'].append(sub[3])
        return dataB
    except Exception as e:
        print(e)
    else:
        return dataB


def hora_actualizada(ade=0):
    ahora = datetime.now()
    dia = ahora.strftime('%A')
    hora = ahora.strftime('%-H:%-M')
    segundo = int(ahora.strftime('%-S'))
    hor = int(hora.split(':')[0])
    mins = int(hora.split(':')[1])
    minsNuevo = mins + ade
    segsNuevo = segundo + ade
    
    if segsNuevo >= 60:
        minsNuevo = minsNuevo + 1
        segusNuevos = segsNuevo - 60
        horaFin = str(hor)+':'+str(minsNuevo)
        segsFin = segusNuevos
    else:
        segsFin = str(segsNuevo)
        
    
    if minsNuevo >= 60:
        horaNueva = hor + 1
        minsNuevos = minsNuevo - 60
        horaFin = str(horaNueva)+':'+str(minsNuevos)
    else:
        horaFin = str(hor)+':'+str(minsNuevo)
    
    return dia, horaFin, segsFin

# funcion que envia las senial del ultrasonico
def send_trigger_pulse():
    GPIO.output(trigger, True)
    sleep(0.0001)
    GPIO.output(trigger, False)
    

# empieza a escuchar 
def wait_for_echo(value, timeout):
    count=timeout
    while GPIO.input(echo) != value and count > 0:
        cout = count - 1


# calcula distancia
def get_distance():
    send_trigger_pulse()
    wait_for_echo(True, 10000)
    start = time()
    wait_for_echo(False, 10000)
    finish = time()
    pulse_len = finish-start
    distance_cm = pulse_len/0.000058
    return round(distance_cm, 2)

# funcion para crear todos los pinModes
def peripheral_setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(trigger, GPIO.OUT)
    GPIO.setup(echo, GPIO.IN)
    for i in [5,6,13,19]:
        GPIO.setup(i, GPIO.OUT)
        GPIO.output(i, 0)
    

    
def moverMotor(peso, listaPin):
    seq = [[1,0,0,0], [1,1,0,0], [0,1,0,0], [0,1,1,0], [0,0,1,0], [0,0,1,1], [0,0,0,1], [1,0,0,1]]
    
    hx = HX711(21, 20)
    hx.set_scale_ratio(-959.7714285714286)
    
    prom = 0
    for i in range(6):
        prom += round(hx.get_weight_mean(20)) - 155
        
    medida = round(prom/6)
    if medida < 0:
        medida = 0
        
    valor = int(peso) - medida
    print(medida)
    print(valor)
    
    if valor > 0:
        dif = valor
    else:
        dif = 0
        
    for i in range(128*2*dif):
        for halfstp in range(8):
            for pin in range(4):
                GPIO.output(listaPin[pin], seq[halfstp][pin])
            sleep(0.001)
    return False
      



# credenciales para la base de datos
cred = credentials.Certificate('embebidos-62cd7-firebase-adminsdk-1bbuc-3fd9915b7f.json')
firebase_admin.initialize_app(cred, {'databaseURL':'https://embebidos-62cd7-default-rtdb.firebaseio.com/'})




 
def main () :
# Setup
    peripheral_setup()
    entreSemana = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    listaPin = [5, 6, 13, 19]
    
    hx = HX711(21, 20)
    dia, horaActual, segundoActual = hora_actualizada()
    hora1 = hora_actualizada(1)[1]
    segundo20 = hora_actualizada(20)[2]
    datos = manejoDatos()
    comer = horaActual in datos['Horas']
    medir = False
    servir = True
    enableDispensar = True
    medidasNivel = []
    indiceDatos = 0
    

# Infinite loop
    try:
        while 1 :
            # Procesos que quiero en cada segundo (actualizar hora, dia y verificar si es hora de servir)
            dia, horaActual, segundoActual = hora_actualizada()
            comer = horaActual in datos['Horas']
            print("actualizando hora")
            sleep(1)
            
            # Procesos que quiero cada minuto (Parar de medir, volver a estar disponible para servir y actualizar hora de 1 min)
            if segundoActual == segundo20:
                medir = False
                segundoActual = hora_actualizada(20)[2]
            
            
            if (horaActual == hora1):
                servir = True
                datos = manejoDatos()
                horaActual = hora_actualizada(1)[1]
                
                 
                
            # Manejo de medicion solo se entra si ya se sirvio la comida
            if medir and not servir:
                print('midiendo...')
                medidasNivel.append(get_distance())
            else:
                if len(medidasNivel) != 0:
                    prom = sum(medidasNivel)/len(medidasNivel)
                    if prom >= 30:
                        try:
                            sms_alert('ALERTA DISPENSADOR DE COMIDA', 'Los niveles de comida son menores del 10% por favor rellenar.', datos['Correo'][indiceDatos])
                        except Exception as e:
                            print(e)
                        enableDispensar = False
                        medidasNivel = []
                    else:
                        enableDispensar = True
                        medidasNivel = []
            
            # Proceso si ya estamos en hora de comer
            if comer and enableDispensar and servir:
                indiceDatos = datos['Horas'].index(horaActual)
                print("hora de comer")
                
                # Servido entre semana
                if datos['Dias'][indiceDatos] == 'Entre semana' and dia in entreSemana:
                    medir = True
                    servir = moverMotor(datos['Peso'][indiceDatos], listaPin)
                    try:
                        sms_alert('Se sirvio la comida', 'La comida de su mascota se sirvio correctamente a las '+horaActual ,datos['Correo'][indiceDatos])
                    except Exception as e:
                        print(printStackTrace(e))
                
                # Servido Fines de semana
                elif datos['Dias'][indiceDatos] == 'Fin de semana' and not(dia in entreSemana):
                    medir = True
                    servir = moverMotor(datos['Peso'][indiceDatos], listaPin)
                    try:
                        sms_alert('Se sirvio la comida', 'La comida de su mascota se sirvio correctamente a las '+horaActual,datos['Correo'][indiceDatos])
                    except Exception as e:
                        print(e)
                
                # Servido todos los dias
                elif datos['Dias'][indiceDatos] == 'Diariamente':
                    medir = True
                    servir = moverMotor(datos['Peso'][indiceDatos], listaPin)
                    try:
                        sms_alert('Se sirvio la comida', 'La comida de su mascota se sirvio correctamente a las '+horaActual,datos['Correo'][indiceDatos])
                    except Exception as e:
                        print(e)
            
    except(KeyboardInterrupt,SystemExit):
        print ("Fin de programa")
        GPIO.cleanup()
            
# Command line execution
if __name__ == '__main__' :
   main()
   
