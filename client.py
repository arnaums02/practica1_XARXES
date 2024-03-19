import string
import sys
import socket
import struct
import time
from ctypes import sizeof

import select
import signal
import threading

# Estats de la fase de registre
SUBS_REQ = 0x00
SUBS_ACK = 0x01
SUBS_REJ = 0x02
SUBS_INFO = 0x03
INFO_ACK = 0X04
SUBS_NACK = 0x05

# Estats del client en la fase de registre
DISCONNECTED = 0xa0
NOT_SUBSCRIBED = 0xa1
WAIT_ACK_SUBS = 0xa2
WAIT_INFO = 0xa3
WAIT_ACK_INFO = 0xa4
SUBSCRIBED = 0xa5
SEND_HELLO = 0xa6

# Mantenir comunicació periòdica
HELLO = 0x10
HELLO_REJ = 0x11

# Enviar al servidor diferents paquets
SEND_DATA = 0x20
SET_DATA = 0x21
GET_DATA = 0x22
DATA_ACK = 0x23
DATA_NACK = 0x24
DATA_REJ = 0x25

# Constants
MAX_LINE_LENGTH = 255
t = 1
u = 2
n = 7
o = 3
p = 3
q = 3
v = 2
r = 2
s = 3
w = 3

# Structs
class ElementStruct:
    def __init__(self):
        self.Id = ""
        self.Data = ""

class Client_Data:
    def __init__(self):
        self.name = ""
        self.Elements = [ElementStruct() for _ in range(7)]
        self.Local_TCP = 0
        self.Status = 0
        self.Mac = ""

class Server_Data:
    def __init__(self):
        self.Mac = ""
        self.rand_Num = ""
        self.Server = ""
        self.Server_UDP = 0
        self.Server_TCP = 0
        self.newServer_UDP = 0

class UDP_PDU:
    def __init__(self):
        self.Type = 0
        self.mac = ""
        self.rand_Num = ""
        self.Data = ""

class TCP_PDU:
    def __init__(self):
        self.Type = 0
        self.mac = ""
        self.rand_Num = ""
        self.Dispositive = ""
        self.Value = ""
        self.Info = ""

# Variables globales
debugMode = False
resetCommunication = False
serverData = Server_Data()
clientData = Client_Data()
clientAddrUDP = None
clientAddrTCP = None
serverAddrUDP = None
serverAddrTCP = None
udpSock = -1
tcpSock = -1    #socket TCP per acceptar les peticions del servidor
tcpSock = -1    #socket TCP per enviar dades al servidor
clientCfgFile = "client.cfg"


def readCfg():
    try:
        with open(clientCfgFile, "r") as fd:
            for line in fd:
                line = line.strip()
                if line.startswith('N'):
                    storeName(line)
                elif line.startswith('S'):
                    storeSituation(line)
                elif line.startswith('E'):
                    storeElements(line)
                elif line.startswith('M'):
                    storeMac(line)
                elif line.startswith('L'):
                    storeLocal(line)
                else:   #Revisar això
                    if line[6] == '-':
                        storeUDP(line)
                    else:
                        storeServer(line)

    except FileNotFoundError:
        print("Error opening the client cfg file")
        exit(-1)

def setupUDPSocket():
    global udpSock, clientAddrUDP

    # Crear el socket UDP
    udpSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if udpSock < 0:
        print("ERROR: No s'ha pogut crear el UDP socket")
        exit(-1)

    # Establim l'adreça del client pel socket
    clientAddrUDP = ('', 0)

    try:
        udpSock.bind(clientAddrUDP)
    except Exception as e:
        print("ERROR: No s'ha pogut realitzar el bind en UDP")
        print(e)
        exit(-1)

    if debugMode:
        print("Socket creat satisfactòriament")

def setupServAddrUDP():
    global serverAddrUDP

    serverAddrUDP = ('', serverData.Server_UDP)
    host = socket.gethostbyname(serverData.Server)
    serverAddrUDP = (host, serverData.Server_UDP)

def loginToServer():
    # Definim la senyal handler cada cop que entrem en la funció loginToServer per si ho hem de repetir
    signal.signal(signal.SIGUSR1, signal.relogin_handler)

    # Inicialitzem udpSock a -1, d'aquesta manera ens assegurem que el socket es crearà unicament 1 cop
    global udpSock
    if udpSock < 0:
        setupUDPSocket()
    setupServAddrUDP()

    # Inicialitzem l'estat del client
    clientData.Status = NOT_SUBSCRIBED
    print("El client no s'ha subscrit")

    subscriberPacket = buildSUB_REQPacket()

    # Enviem el 1r paquet
    try:
        udpSock.sendto(subscriberPacket, serverAddrUDP)
    except Exception as e:
        print("Error enviant el paquet de subscripció per UDP")
        print(e)
        exit(-1)

    if debugMode:
        print("El primer paquet de subscripció ha estat enviat")

    # Canviem l'estat ja que hem enviat el 1r paquet
    clientData.Status = WAIT_ACK_SUBS
    print("L'estat del client ha canviat a WAIT_ACK_SUBS")

    for signUps in range(o):  # Procés de registre -> No se si o esta correcte, o son el numero de proccessos de subscripció que acceptarà abans d'abandonar
        acc = 0
        if debugMode:
            print("Nou registre en proces: número", signUps)
        for packetPerSignUps in range(n):  # Número de paquets por cada procés de registre
            # Per cada paquet que enviem, reiniciem el temps per evitar que es quedi a 0
            time_sec = t
            time_usec = 0
            if packetPerSignUps > p and q * t > acc:  # Incrementem l'interval d'enviament un cop hem arribat als p paquets (Màxim -> q * t)
                acc += t
                time_sec += acc

            ready, _, _ = select.select([udpSock], [], [], time_sec)
            if ready:  # Si rebem un paquet, el processem
                receiveSubscriptionPacket()
                # Per defecte, sortim de la funció de login sinó és que hem de continuar ja que estem en el mateix procés de subscripció
                if not resetCommunication:
                    return

            # Si no s'ha enviat, n'enviem un altre
            try:
                udpSock.sendto(subscriberPacket, serverAddrUDP)
            except Exception as e:
                print("Error enviant la subscripció UDP")
                print(e)
                exit(-1)

            if debugMode:
                print(f"{getTypeOfPacketUDP(subscriberPacket)} paquet N. {packetPerSignUps} enviat. t = {acc + t}")

            # Si continuem en el mateix procés de subscripció després de rebre un paquet, necessitem reiniciar l'estatus del client
            if resetCommunication:
                clientData.Status = WAIT_ACK_SUBS
                print("L'estatus del client ha canviat a WAIT_ACK_SUBS")
                resetCommunication = False
                setupServAddrUDP()
        time.sleep(u)
    print("No es pot connectar amb el servidor.")
    exit(-1)


def receiveSubscriptionPacket():
    global serverAddrUDP

    try:
        packet, _ = udpSock.recvfrom(sizeof(UDP_PDU))
    except Exception as e:
        print("Error a l'hora de rebre el paquet de registre UDP.")
        print(e)
        exit(-1)

    if debugMode:
        print("El paquet UDP s'ha rebut correctament.")

    processPacketType(packet)

#Rebem el paquet HELLO
def receiveHELLOPacket():
    try:
        packet = udpSock.recvfrom(sizeof(UDP_PDU))
        if debugMode:
            print("El paquet UDP de tipus", getTypeOfPacketUDP(packet), "s'ha rebut correctament")
        return packet

    except Exception as e:
        print("Error al rebre el paquet HELLO mitjançant UDP:", e)
        exit(-1)

# Classifiquem els paquets segons el seu tipus
def processPacketType(packet):
    packetType = packet.Type

    if packetType == SUBS_ACK:
        processSUBS_ACK(packet)  # funció implementada
    elif packetType == SUBS_NACK:
        processSUBS_NACK()  # implementar funció
    elif packetType == SUBS_REJ:
        processSUBS_REJ()  # implementar funció
    elif packetType == INFO_ACK:
        processINFO_ACK(packet)  # implementar funció

def processSUBS_ACK(packet):
    global clientData, serverData, serverAddrUDP

    if clientData.Status != WAIT_ACK_SUBS:
        print("Error en l'estat del client o del paquet.")
        loginToServer()
        return

    # Copiem l'adreça MAC, ID del server i la seva IP
    serverData.Mac = packet.mac.decode('utf-8')
    serverData.rand_Num = packet.rand_Num.decode('utf-8')
    serverIP = serverAddrUDP[0]  # IP del servidor obtenida de serverAddrUDP
    serverData.Server = serverIP
    serverData.newServer_UDP = int(packet.Data)

    SUBS_INFOPacket = buildSUBS_INFOPacket()

    # Modifiquem serverAddrUDP amb el nou port UDP que hem rebut del servidor i continuem amb la communicació
    serverAddrUDP = (serverIP, serverData.newServer_UDP)

    # Enviem els paquets SUBS_INFO al servidor
    try:
        udpSock.sendto(SUBS_INFOPacket, serverAddrUDP)
    except Exception as e:
        print("Error al enviar los paquetes UDP SUBS_INFO")
        print(e)
        exit(-1)

    clientData.Status = WAIT_ACK_INFO
    print("L'estat del Client ha cambiat a WAIT_ACK_INFO")

    loginToServer()

def processSUBS_NACK():
    global clientData, resetCommunication

    clientData.Status = NOT_SUBSCRIBED
    print("L'estat del client és NOT_SUBSCRIBED\n")
    resetCommunication = True


def processSUBS_REJ():
    loginToServer()

def processINFO_ACK(packet):
    global clientData, resetCommunication

    if clientData.Status != WAIT_ACK_INFO or not correctDataServer(packet):
        print("Client o paquet erroni!!")
        loginToServer()
        return

    clientData.Status = SUBSCRIBED
    print("L'estat del client és SUBSCRIBED\n")
    serverData.Server_TCP = int(packet.Data)
    periodicCommunication()

def buildSUB_REQPacket():   #revisar
    packet = UDP_PDU()
    packet.Type = SUBS_REQ
    packet.mac = clientData.Mac.encode('utf-8')
    packet.rand_Num = "00000000".encode('utf-8')
    packet.Data = ""    # emplena les dades de l'arxiu .cfg, si és necessari
    return packet

def buildSUBS_INFOPacket(): #revisar
    packet = UDP_PDU()
    packet.Type = SUBS_INFO
    packet.mac = clientData.Mac.encode('utf-8')
    packet.rand_Num = "00000000".encode('utf-8')

    data = str(clientData.Local_TCP) + ","
    for element in clientData.Elements:
        data += element.Id.decode('utf-8') + ";"

    data = data[:-1]
    packet.Data = data.encode('utf-8')
    return packet

def buildHELLOPacket(): #revisar, sobretot data
    packet = UDP_PDU();
    packet.Type = HELLO
    packet.mac = clientData.Mac.encode('utf-8')
    packet.rand_Num = serverData.rand_Num.encode('utf-8')
    packet.Data = "".encode('utf-8')
    return packet

# Comprovem si la informació emmagatzemada del servidor i la rebuda en el paquet coincideixen
def correctDataServer(packet):
    receivedServerIp = serverAddrUDP[0] #Obtenim la IP del servidor
    if (packet.mac == serverData.Mac and
            packet.rand_Num == serverData.rand_Num and
            serverData.Server == receivedServerIp):
        return True
    return False

#Iniciem la communicació periòdica
def periodicCommunication():
    HELLOPacket = buildHELLOPacket()
    setupServAddrUDP()  # Reinicia la direcció del servidor per la comunicació periòdica

    try:
        udpSock.sendto(HELLOPacket, serverAddrUDP)
        if debugMode:
            print("UDP packet type", getTypeOfPacketUDP(HELLOPacket), "sent correctly.")

        time = r * v
        time.sleep(time)

        ready, _, _ = select.select([udpSock], [], [], time)
        if udpSock in ready:
            packet = receiveHELLOPacket()
            # Primer ALIVE recibido correctamente
            if packet.Type == HELLO and correctDataServer(packet) and clientData.Id == packet.Data:
                createThreads()
                return
    except Exception as e:
        print("Error sending or receiving ALIVE packet:", e)

    # Paquete no recibido en R*V segundos o paquete incorrecto
    print("First ALIVE not received or incorrect packet")
    time.sleep(v)
    loginToServer()

#Retornem la string de cada paquet
def getTypeOfPacketUDP(packet):
    if packet.Type == SUBS_ACK:
        return "SUBS_ACK"
    elif packet.Type == SUBS_INFO:
        return "SUBS_INFO"
    elif packet.Type == SUBS_NACK:
        return "SUBS_NACK"
    elif packet.Type == SUBS_REQ:
        return "SUBS_REQ"
    elif packet.Type == SUBS_REJ:
        return "SUBS_REJ"
    elif packet.Type == INFO_ACK:
        return "INFO_ACK"
    elif packet.Type == HELLO:
        return "HELLO"
    elif packet.Type == HELLO_REJ:
        return "HELLO_REJ"

    return None

#Creem els threads per enviar els packets HELLO al servidor i gestionem l'entrada d'usuari
def createThreads():
    if clientData.Status != SUBSCRIBED:
        print("Estat del client ERRONI!!")
        loginToServer()
        return

    clientData.Status = SEND_HELLO
    print("L'estat del client és SEND_HELLO")

    if tcpSock < 0:
        openTCP1Socket()

    terminalThread = threading.Thread(target=handleTerminalInput)
    sendHelloThread = threading.Thread(target=sendHELLO)

    terminalThread.start()
    sendHelloThread.start()

    handleTCPConnections()


