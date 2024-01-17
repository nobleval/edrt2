import time
import datetime
import requests

# Ecodevice
ecodevice = '192.168.1.19'

# Répertoire des sauvegardes
workingdir= 'D:/My Documents/~Perso/2023/gce config'

# Known positions
TICCurrentIndexPosition = 0x101F27
TICCurrentPricePosition = 0x101EA7
historyPosition = 0x108000
logPosition = 0x1026C0

# Offset (bytes count)
TICHourConsPriceOffset = (8 * 16) + 8 # from hour index
TICDayIndexPriceOffset = (20 * 16) + 12 # from midnight index

# Sizes (bytes count)
TICCurrentIndexOrPriceLength = 4
TICHourConsOrPriceLength = 2
TICDayIndexLength = 6
TICDayPriceLength = 4
hour00ByteLength = 26 * 16 # midnight index and counters values
hourByteLength = 10 * 16
dayByteLength = hour00ByteLength + (23 * hourByteLength)

TIC_label_order={'HCJB':1, 'HPJB':2, 'HCJW':3, 'HPJW':4, 'HCJR':5, 'HPJR':6}

def dateAsBytes(datetime):
    return bytes.fromhex(f'{datetime.year-2000:02x}' + f'{datetime.month:02x}' + f'{datetime.day:02x}' + '00')
    
def dateTimeAsBytes(datetime):
    return bytes.fromhex(f'{datetime.year-2000:02x}' + f'{datetime.month:02x}' + f'{datetime.day:02x}' + f'{datetime.hour:02x}')
    
def dateIndex(datetime):
    index=historyPosition
    bDatetime=dateAsBytes(datetime)
    while not (arrSystemGCE[index:index+len(bDatetime)] == bDatetime) and index < len(arrSystemGCE):
        index=index+dayByteLength
        found=True
    if found:
        return index
    else:
        return -1

def dateTimeIndex(datetime):
    dayIndex=dateIndex(datetime)
    bDatetime=dateTimeAsBytes(datetime)
    index=dayIndex + hour00ByteLength
    while not (arrSystemGCE[index:index+len(bDatetime)] == bDatetime) and index < dayIndex + dayByteLength:
        index=index+hourByteLength
        found=True
    if found:
        return index
    else:
        return -1

def indexesOfCurrentTIC(label):
    offset = (TIC_label_order[label] - 1) * TICCurrentIndexOrPriceLength
    return TICCurrentIndexPosition + offset, TICCurrentPricePosition + offset

def indexesOfDayTIC(label, datetime):
    offset = TICDayIndexPriceOffset + (TIC_label_order[label] - 1) * (TICDayIndexLength + TICDayPriceLength)
    index = dateIndex(datetime) + offset
    return index, index + TICDayIndexLength

def indexesOfHourTIC(label, datetime):
    offset=TICHourConsPriceOffset + (TIC_label_order[label] - 1) * TICHourConsOrPriceLength * 2
    index=dateTimeIndex(datetime) + offset
    return index, index + TICHourConsOrPriceLength

def set_bytes(value, index):
    global arrSystemGCE
    arrSystemGCE[index:index+len(value)]=value

def update_current_TIC(label, TICindex, price):
    indexes = indexesOfCurrentTIC(label)
    # index value
    set_bytes(TICindex.to_bytes(TICCurrentIndexOrPriceLength, byteorder='big'), indexes[0])
    # price value
    price = int(price * 100) #in cents
    set_bytes(price.to_bytes(TICCurrentIndexOrPriceLength, byteorder='big'), indexes[1])

def update_day_TIC(label, TICindex, price, datetime):
    indexes = indexesOfDayTIC(label, datetime)
    # index value
    set_bytes(TICindex.to_bytes(TICDayIndexLength, byteorder='big'), indexes[0])
    # price value
    price = int(price * 100) #in cents
    set_bytes(price.to_bytes(TICDayPriceLength, byteorder='big'), indexes[1])

def update_multiple_days_TIC(label, TICindex, price, start_datetime, end_datetime):
    day = start_datetime
    while day <= end_datetime:
        update_day_TIC(label, TICindex, price, day)
        day=day+datetime.timedelta(days=1)

def update_hour_TIC(label, cons, price, datetime):
    indexes = indexesOfHourTIC(label, datetime)
    # index value
    set_bytes(cons.to_bytes(TICHourConsOrPriceLength, byteorder='big'), indexes[0])
    # price value
    price = int(price * 100) #in cents
    set_bytes(price.to_bytes(TICHourConsOrPriceLength, byteorder='big'), indexes[1])

def get_current_TIC(label):
    indexes = indexesOfCurrentTIC(label)
    index=indexes[0]
    TICindex = int.from_bytes(arrSystemGCE[index:index+TICCurrentIndexOrPriceLength], byteorder='big')
    index=indexes[1]
    price = int.from_bytes(arrSystemGCE[index:index+TICCurrentIndexOrPriceLength], byteorder='big')
    return TICindex, price/100

def get_day_TIC(label, datetime):
    indexes = indexesOfDayTIC(label, datetime)
    index=indexes[0]
    TICindex = int.from_bytes(arrSystemGCE[index:index+TICDayIndexLength], byteorder='big')
    index=indexes[1]
    price = int.from_bytes(arrSystemGCE[index:index+TICDayPriceLength], byteorder='big')
    return TICindex, price/100

def get_hour_TIC(label, datetime):
    indexes = indexesOfHourTIC(label, datetime)
    index=indexes[0]
    cons = int.from_bytes(arrSystemGCE[index:index+TICHourConsOrPriceLength], byteorder='big')
    index=indexes[1]
    price = int.from_bytes(arrSystemGCE[index:index+TICHourConsOrPriceLength], byteorder='big')
    return cons, price/100

def download_systemGCE_file(filename):
    global arrSystemGCE

    print('Téléchargement en cours...')
    response = requests.get('http://' + ecodevice + '/admin/download/system.gce')
    if not response.status_code == 200:
        print('Le téléchargement a échoué. Erreur : ' + str(response.status_code))
        return
    with open(filename, "wb") as outfile:
        outfile.write(response.content)
    arrSystemGCE=bytearray(response.content)

def load_systemGCE_file(filename):
    global arrSystemGCE
    
    with open(filename, "rb") as infile:
        content=infile.read()
    arrSystemGCE=bytearray(content)    

def write_systemGCE_file(filename):
        with open(filename, "wb") as outfile:
            outfile.write(arrSystemGCE)

def upload_systemGCE_content():
    server='localhost:80'
    arrTest=bytearray([15,22,44,88,66,77,20,66,30,32,33,55])
    print('Chargement en cours...') 
    response = requests.post('http://' + server + '/admin/upload.htm', files={'i': ('arrSystemGCE', arrTest, 'application/octet-stream')})                       
    if not response.status_code == 200:
        print('La restauration globale a échoué. Erreur : ' + str(response.status_code))
        return
    print('Redémarrage en cours...')
    response = requests.get('http://' + server + '/admin/reboot.cgi')
    if not response.status_code == 200:
        print('Le redémarrage a échoué. Erreur : ' + str(response.status_code))
        return

def main():
    global arrSystemGCE

    # -------------------------
    # Téléchargement de la configuration globale (ou travail sur un fichier existant)
    #--------------------------    
    choice=input('Télécharger une sauvegarde globale ? [o/n]\n')
    if choice == 'o':
        filename = workingdir + '/system_' + datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        download_systemGCE_file(filename + '.gce')
        print('Le fichier a été enregistré et nommé ' + filename + '.gce')
    else: #work with an existing file
        filename = workingdir + '/system_2023-10-14T21-55-31' # replace by the desired file
        choice=input('Utiliser le fichier ' + filename + '.gce ? [o/n]\n')
        if not choice == 'o':
            return
        
    load_systemGCE_file(filename + '.gce')

    # -------------------------
    # Visualisation des erreurs
    #--------------------------
    #faulty_datetime1=datetime.datetime(2023,10,14,8)
    faulty_datetime1=datetime.datetime(2023,10,14,15)

    dayTIC1=get_day_TIC('HCJW', faulty_datetime1) # before the error

    print('\nAvant modifications :')
    print(faulty_datetime1.strftime("%Y-%m-%d") + ' index à minuit : ' + str(dayTIC1))
    print('Index actuel : ' + str(get_current_TIC('HCJW')))
    print(faulty_datetime1.strftime("%Y-%m-%d %H:00") + ' conso : ' + str(get_hour_TIC('HCJW', faulty_datetime1)))

    # -------------------------
    # Corrections
    # -------------------------
    update_current_TIC('HCJW', dayTIC1[0], dayTIC1[1])
    update_hour_TIC('HCJW', 0, 0, faulty_datetime1)

##    next_day=faulty_datetime + datetime.timedelta(days=1)
##    update_day_TIC('HCJW', 123450, 1.3, next_day)
##    
##    yesterday=datetime.datetime.now() - datetime.timedelta(days=1)
##    update_multiple_days_TIC('HCJW', 123450, 1.3, next_day, yesterday)

    # -------------------------
    # Visualisation des corrections
    # -------------------------
    print('\nAprès modifications :')
    print('Index actuel : ' + str(get_current_TIC('HCJW')))
##    print(get_day_TIC('HCJW', faulty_datetime))
    print(faulty_datetime1.strftime("%Y-%m-%d %H:00") + ' conso : ' + str(get_hour_TIC('HCJW', faulty_datetime1)))


    # -------------------------
    # Chargement dans l'ecodevice ou sauvegarde dans un nouveau fichier
    # -------------------------
    choice=input('Charger dans l\'ecodevice ? [o/n]\n')
    if choice == 'o':
        choice=input('Confirmer ? [o/n]\n')
        if choice == 'o':
            upload_systemGCE_content()
    else:
        choice=input('Sauvegarder dans un fichier ? [o/n]\n')
        if choice == 'o':
            filename = filename + '_modifié_' + datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
            write_systemGCE_file(filename + '.gce')
            print('\nModifications sauvegardées dans le fichier ' + filename + '.gce')
            print('Restaurer la configuration globale manuellement dans l\'Ecodevice.')


main()
