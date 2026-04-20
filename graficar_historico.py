import matplotlib.pyplot as plt
import datetime
import os

LOG_FILE = './temp.log'

def graficar():
    if not os.path.exists(LOG_FILE):
        print("No hay datos en la bitácora todavía.")
        return

    tiempos = []
    temperaturas = []

    with open(LOG_FILE, 'r') as f:
        for linea in f:
            partes = linea.split()
            if len(partes) >= 2:
                # Convertir tiempo UNIX a hora legible
                hora = datetime.datetime.fromtimestamp(float(partes[0]))
                temp = float(partes[1])
                if len(partes) == 2:  # exactamente timestamp y temperatura
                    hora = datetime.datetime.fromtimestamp(float(partes[0]))
                    temp = float(partes[1])
                tiempos.append(hora)
                temperaturas.append(temp)

    plt.figure(figsize=(10, 6))
    plt.plot(tiempos, temperaturas, color='blue', marker='.', linestyle='-')
    plt.title('Histórico de Temperatura - Sensor LM35')
    plt.xlabel('Hora del registro')
    plt.ylabel('Temperatura (°C)')
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    nombre_archivo = 'grafica_temperatura.png'
    #Guardando gráfica
    plt.savefig(nombre_archivo)
    print(f"Grafica guardada exitosamente como: {nombre_archivo}")

if __name__ == '__main__':
    graficar()
