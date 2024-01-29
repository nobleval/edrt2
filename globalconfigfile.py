""" Ce script fournit des fonctions pour lire et modifier des relevés de
l'historique d'un fichier de configuration globale exporté ou téléchargé
depuis un Ecodevice RT2, par exemple pour effectuer des corrections.

Se référer au readme.

Publié sur https://github.com/nobleval
@Author: nobleval
"""

import time
import datetime
import requests
import csv

#
# DONNEES PERSONNELLES A MODIFIER
#

# Adresse IP de l'Ecodevice pour télécharger la configuration globale à
# partir du script
ecodevice = '192.168.1.19'

# Répertoire des sauvegardes et de travail
workingdir= 'D:/My Documents/~Perso/2023/gce config'

# Nom du fichier de sauvegarde globale déjà téléchargé sur lequel
# travailler (si il existe), sans extension .gce
existing_filename = 'system_2024-01-27T10-01-34'

# Noms des index TIC associés à leur numéro d'ordre dans l'Ecodevice
TIC_label_order={'Inactif':0, 'HCJB':1, 'HPJB':2, 'HCJW':3, 'HPJW':4, 'HCJR':5, 'HPJR':6}

# --------------------------------------------------------

#
# Fonctions de base pour les opérations de lecture et de mise à jour
#

# Positions connues
TICCurrentIndexPosition = 0x101F23
TICCurrentPricePosition = 0x101EA3
historyPosition = 0x108000
logPosition = 0x1026C0

# Offset (nombre d'octets)
TICHourConsPriceOffset = (8 * 16) + 4 # depuis une position d'une heure
TICDayIndexPriceOffset = (20 * 16) + 2 # depuis une position de 0h

# Tailles (nombre d'octets)
TICCurrentIndexOrPriceLength = 4
TICHourConsOrPriceLength = 2
TICDayIndexLength = 6
TICDayPriceLength = 4
hour00ByteLength = 26 * 16 
hourByteLength = 10 * 16
dayByteLength = hour00ByteLength + (23 * hourByteLength)

# Valeur spéciale en l'absence de mesure (coupure de courant par exemple)
absentValue = 0xFFFF # 65535

# Retourne une date en octets
def dateAsBytes(datetime):
    return bytes.fromhex(f'{datetime.year-2000:02x}' + f'{datetime.month:02x}' + f'{datetime.day:02x}' + '00')

# Retourne une date et heure en octets    
def dateTimeAsBytes(datetime):
    return bytes.fromhex(f'{datetime.year-2000:02x}' + f'{datetime.month:02x}' + f'{datetime.day:02x}' + f'{datetime.hour:02x}')

# Retourne la position dans le fichier d'une date dans l'historique    
def datePosition(datetime):
    position=historyPosition
    bDatetime=dateAsBytes(datetime)
    found=arrGlobalConf[position:position+len(bDatetime)] == bDatetime
    while not found and position < len(arrGlobalConf):
        position=position+dayByteLength
        found=arrGlobalConf[position:position+len(bDatetime)] == bDatetime
    if found:
        return position
    else:
        return -1

# Retourne la position dans le fichier d'une date et heure dans l'historique
def dateTimePosition(datetime):
    dayPosition=datePosition(datetime)
    bDatetime=dateTimeAsBytes(datetime)
    position=dayPosition + hour00ByteLength
    found=arrGlobalConf[position:position+len(bDatetime)] == bDatetime
    while not found and position < dayPosition + dayByteLength:
        position=position+hourByteLength
        found=arrGlobalConf[position:position+len(bDatetime)] == bDatetime
    if found:
        return position
    else:
        return -1

# Retourne les positions dans le fichier de l'index TIC courant et du prix cumulé, pour un index TIC donné
def positionsOfCurrentTIC(label):
    offset = (TIC_label_order[label]) * TICCurrentIndexOrPriceLength
    return TICCurrentIndexPosition + offset, TICCurrentPricePosition + offset

# Retourne les positions dans le fichier de l'index TIC et du prix cumulé, pour un index TIC et un jour donnés
def positionsOfDayTIC(label, datetime):
    offset = TICDayIndexPriceOffset + (TIC_label_order[label]) * (TICDayIndexLength + TICDayPriceLength)
    position = datePosition(datetime) + offset
    return position, position + TICDayIndexLength

# Retourne les positions dans le fichier de la consommation horaire et du prix, pour un index TIC et un jour et heure donnés
def positionsOfHourTIC(label, datetime):
    offset=TICHourConsPriceOffset + (TIC_label_order[label]) * TICHourConsOrPriceLength * 2
    position=dateTimePosition(datetime) + offset
    return position, position + TICHourConsOrPriceLength

# Modifie une valeur en octets à une position donnée
def set_bytes(value, position):
    global arrGlobalConf
    arrGlobalConf[position:position+len(value)]=value

# Met à jour l'index TIC courant et le prix cumulé donné en euros, pour un index TIC donné
def update_current_TIC(label, TICindex, price):
    positions = positionsOfCurrentTIC(label)
    # valeur d'index
    set_bytes(TICindex.to_bytes(TICCurrentIndexOrPriceLength, byteorder='big'), positions[0])
    # prix
    price = int(price * 100) # en cents
    set_bytes(price.to_bytes(TICCurrentIndexOrPriceLength, byteorder='big'), positions[1])

# Met à jour l'index TIC et le prix cumulé donné en euros, pour un index TIC et un jour donné
def update_day_TIC(label, TICindex, price, datetime):
    positions = positionsOfDayTIC(label, datetime)
    # valeur d'index
    set_bytes(TICindex.to_bytes(TICDayIndexLength, byteorder='big'), positions[0])
    # prix
    price = int(price * 100) # en cents
    set_bytes(price.to_bytes(TICDayPriceLength, byteorder='big'), positions[1])

# Met à jour l'index TIC et le prix cumulé donné en euros, pour un index
# TIC donné et plusieurs jours (inclus), avec la même valeur (mise à
# jour en cascade d'un index TIC qui n'a pas varié)
def update_multiple_days_TIC(label, TICindex, price, start_datetime, end_datetime):
    day = start_datetime
    while day <= end_datetime:
        update_day_TIC(label, TICindex, price, day)
        day=day+datetime.timedelta(days=1)

# Met à jour la consommation horaire et le prix en euros, pour un index TIC et un jour et heure donnés 
def update_hour_TIC(label, cons, price, datetime):
    if datetime.hour == 0:
        raise Exception(f'{label} {datetime:%Y-%m-%d %H:00} : l\'historique n\'enregistre pas de consommation horaire à 0h ! Uniquement des index.')
    positions = positionsOfHourTIC(label, datetime)
    # valeur d'index
    set_bytes(cons.to_bytes(TICHourConsOrPriceLength, byteorder='big'), positions[0])
    # prix
    price = int(price * 100) # en cents
    set_bytes(price.to_bytes(TICHourConsOrPriceLength, byteorder='big'), positions[1])

# Lit les valeurs de l'index TIC courant et du prix cumulé en cents, pour un index TIC donné
def get_current_TIC(label):
    positions = positionsOfCurrentTIC(label)
    position=positions[0]
    TICindex = int.from_bytes(arrGlobalConf[position:position+TICCurrentIndexOrPriceLength], byteorder='big')
    position=positions[1]
    price = int.from_bytes(arrGlobalConf[position:position+TICCurrentIndexOrPriceLength], byteorder='big')
    return TICindex, price # en cents

# Lit les valeurs de l'index TIC et du prix cumulé en cents, pour un index TIC et jour donnés
def get_day_TIC(label, datetime):
    positions = positionsOfDayTIC(label, datetime)
    position=positions[0]
    TICindex = int.from_bytes(arrGlobalConf[position:position+TICDayIndexLength], byteorder='big')
    position=positions[1]
    price = int.from_bytes(arrGlobalConf[position:position+TICDayPriceLength], byteorder='big')
    return TICindex, price # en cents

# Lit la consommation horaire et le prix en cents, pour un index TIC et un jour et heure donnés
def get_hour_TIC(label, datetime):
    if datetime.hour == 0:
        raise Exception(f'{label} {datetime:%Y-%m-%d %H:00} : l\'historique n\'enregistre pas de consommation horaire à 0h ! Uniquement des index.')
    positions = positionsOfHourTIC(label, datetime)
    position=positions[0]
    cons = int.from_bytes(arrGlobalConf[position:position+TICHourConsOrPriceLength], byteorder='big')
    if cons == absentValue:
        cons = 0
    position=positions[1]
    price = int.from_bytes(arrGlobalConf[position:position+TICHourConsOrPriceLength], byteorder='big')
    if price == absentValue:
        price = 0
    return cons, price # en cents

#
# Fonctions annexes
#

# Retourne un jour d'après ou d'avant suivant l'offset en jour donné
def next_day(date, deltaday):
    return date + datetime.timedelta(days=deltaday)

# Retourne un jour et heure d'après ou d'avant suivant l'offset en heure donné
def next_hour(datetime1, deltahour):
    return datetime1 + datetime.timedelta(hours=deltahour)

# Convertit un prix donné en cents en euros (pour supprimer les effets de bord de la conversion en nombre à virgule)
def price_in_euros(price):
    if price < 0:
        strprice=str(price)[1:]
        sign='-'
    else:
        strprice=str(price)
        sign=''
        
    if len(strprice) > 2:
        return float(sign + strprice[0:len(strprice)-2] + '.' + strprice[-2:])
    if len(strprice) == 1:
        return float(sign + '0.0' + strprice)
    if len(strprice) == 2:
        return float(sign + '0.' + strprice)
    
#
# Calcul de la consommation quotidienne et de la consommation horaire
# entre 23:00 et 00:00
#

# Retourne la consommation horaire et le prix en cents calculés par
# différence entre les index et les prix de 2 jours consécutifs, pour un
# index TIC et jour donnés
def daily_cons_TIC(label, date):
    day1_TIC=get_day_TIC(label, date)
    day2_TIC=get_day_TIC(label, next_day(date, 1))
    return day2_TIC[0] - day1_TIC[0], day2_TIC[1] - day1_TIC[1]

# Retourne le somme des consommations horaires et prix en cents de 00:00
# à 23:00 (relevés de 01:00 à 23:00), pour un index TIC et jour donnés
def day_sum_00_to_23_TIC(label,date):
    datetime1=datetime.datetime(date.year, date.month, date.day, 1)
    cons=0
    price=0
    for h in range(1,24):
        hour_TIC = get_hour_TIC(label, datetime1)
        cons=cons+hour_TIC[0]  
        price=price+hour_TIC[1]
        datetime1=next_hour(datetime1, 1)
    return cons, price

# Retourne la consommation horaire et prix en cents entre 23:00 et
# 00:00, pour un index TIC et jour donnés
def hour_cons_between_23_and_00_TIC(label, date):
    #sum from 00:00 to 23:00
    day_sum = day_sum_00_to_23_TIC(label,date)
    #consumption of the day
    daily_cons=daily_cons_TIC(label, date)
    return daily_cons[0] - day_sum[0], daily_cons[1] - day_sum[1]

#
# Fonctions pour exporter les mesures TIC dans un fichier csv, pour
# visualiser les erreurs ou les corrections
#

# Retourne les mesures TIC d'un jour donné, et les valeurs calculées
# pour la consommation relevée à 00:00
def get_dayTIC_all(date):
    dic = {}
    dic['Heure du relevé'] = date.strftime('%Y-%m-%d 00:00')
    dic['EDRT2'] = next_hour(date, -1).strftime('%Hh')
    for tic_label in TIC_label_order:
        dayTIC = get_day_TIC(tic_label, date)
        daily_cons=daily_cons_TIC(tic_label, next_day(date, -1))
        hour_cons=hour_cons_between_23_and_00_TIC(tic_label, next_day(date, -1))
        dic[tic_label + ' index'] = dayTIC[0]
        dic[tic_label + ' cumul prix'] = dayTIC[1] # en cents
        dic[tic_label + ' conso jour'] = daily_cons[0] # calculé
        dic[tic_label + ' prix jour'] = daily_cons[1] # calculé, en cents
        dic[tic_label + ' conso'] = hour_cons[0] # calculé
        dic[tic_label + ' prix'] = hour_cons[1] # calculé, en cents
    return dic

# Retourne les mesures TIC pour une heure donnée
def get_hourTIC_all(datetime):
    dic = {}
    dic['Heure du relevé'] = datetime.strftime('%Y-%m-%d %H:00')
    dic['EDRT2'] = next_hour(datetime, -1).strftime('%Hh')
    for tic_label in TIC_label_order:
        hourTIC = get_hour_TIC(tic_label, datetime)
        dic[tic_label + ' conso'] = hourTIC[0]
        dic[tic_label + ' prix'] = hourTIC[1] # en cents
    return dic

# Retourne les index TIC courants et les prix cumulés (associés à une
# heure fictive de relevé qui est "maintenant")
def get_currentTIC_all():
    dic = {}
    dic['Heure du relevé'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    dic['EDRT2'] = 'courant'
    for tic_label in TIC_label_order:
        currentTIC = get_current_TIC(tic_label)
        dic[tic_label + ' index'] = currentTIC[0]
        dic[tic_label + ' cumul prix'] = currentTIC[1] # en cents
    return dic    

# Retourne la liste des mesures TIC entre une date de début et une date
# de fin
def get_TICmeasures_all(startDate, endDate):
    TICmeasures = []
    startDateTime=datetime.datetime(startDate.year, startDate.month, startDate.day, 0, 0)
    endDateTime=datetime.datetime(endDate.year, endDate.month, endDate.day, 0, 0)
    h = startDateTime
    while h < next_hour(endDateTime, 1):
        if h.hour==0:
            TICmeasures.append(get_dayTIC_all(h)) # quotidien et horaire à 00:00
        else:
            TICmeasures.append(get_hourTIC_all(h)) # horaire
        h = next_hour(h, 1)
    TICmeasures.append(get_currentTIC_all()) # index TIC courants et prix cumulés (associés à une heure fictive de relevé qui est "maintenant")
    return TICmeasures

# Retourne une liste des mesures TIC avec marquage des incohérences, à
# partir d'une liste existante de mesures Les vérifications portent sur
# des index ou des prix cumulés qui seraient décroissants ainsi que des
# valeurs négatives obtenues lors des calculs
def get_TICerrors(measures):
    TICerrors = []
    previous_values = {}
    for tic_label in TIC_label_order:
        previous_values[tic_label + ' index'] = 0
        previous_values[tic_label + ' cumul prix'] = 0    
    for m in measures:
        result = {}
        result['Heure du relevé']=m['Heure du relevé']
        result['EDRT2']=m['EDRT2']
        for key, value in m.items():
            if key == 'Heure du relevé' or key == 'EDRT2':
                continue
            if key.endswith('index') or key.endswith('cumul prix'):
                if value < previous_values[key]: # index ou prix cumulé décroissant
                    result[key]='ERREUR'
                else:
                    result[key]=value
                previous_values[key] = value
                continue
            if value < 0:
                result[key]='ERREUR'    # valeur négative
            else:
                result[key]=value
        TICerrors.append(result)
    return TICerrors       

# Exporte une liste de mesures TIC dans un fichier csv
def outputTICmeasuresInCsv(measures, fullfilename):
    #csv header
    field_names = []
    field_names.append('Heure du relevé')
    field_names.append('EDRT2')
    delimiter = ';'
    for tic_label in TIC_label_order:
        field_names.append(tic_label + ' index')
        field_names.append(tic_label + ' cumul prix')
        field_names.append(tic_label + ' conso jour')
        field_names.append(tic_label + ' prix jour')
        field_names.append(tic_label + ' conso')
        field_names.append(tic_label + ' prix')

    #output the csv file
    with open(fullfilename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, delimiter=delimiter, fieldnames = field_names)
        writer.writeheader()
        writer.writerows(measures)

#
# Affichage de valeurs dans la console
#

# Retourne une paire (Wh, prix en cents) avec le prix en euros
def format_Wh_price_pair(pair):
    return '(' + f'{pair[0]:d}' + ', ' + f'{price_in_euros(pair[1]):.2f}' + ')'
    #return '(' + f'{pair[0]:d}' + ', ' + f'{pair[1]/100:.2f}' + ')'

# Affiche tous les index TIC courants et les prix cumulés
def print_current_index_TIC_all():
    for tic_label in TIC_label_order:
        currentTIC=get_current_TIC(tic_label)
        print(tic_label + ' (index, prix) : ' + format_Wh_price_pair(currentTIC))    

# Affiche tous les index TIC et prix cumulés pour un jour donné
def print_day_TIC_all(date):
    print(date.strftime("\n%Y-%m-%d 00:00"))
    for tic_label in TIC_label_order:
        dayTIC = get_day_TIC(tic_label, date)
        daily_cons=daily_cons_TIC(tic_label, next_day(date, -1))
        print(tic_label + ' (index, prix) : ' + format_Wh_price_pair(dayTIC) + ' conso jour précédent (conso, prix) : ' + format_Wh_price_pair(daily_cons))

# Affiche toutes les consommations horaires et prix, pour un jour et
# heure donnés
def print_hour_TIC_all(datetime):
    print(datetime.strftime("\n%Y-%m-%d %H:00") + ' (<=> dans csv ou graphe ' + next_hour(datetime, -1).strftime("%d/%m/%Y %Hh)"))
    for tic_label in TIC_label_order:
        hourTIC = get_hour_TIC(tic_label, datetime)
        print(tic_label + ' (conso, prix) : ' + format_Wh_price_pair(hourTIC))        

# Affiche toutes les sommes de consommations horaires et prix calculés
# de 00:00 à 23:00 pour un jour donné
def print_day_sum_00_to_23_TIC_all(date):
    print(date.strftime("\n%Y-%m-%d somme de 0h à 23h"))
    for tic_label in TIC_label_order:
        day_sum_00_to_23 = day_sum_00_to_23_TIC(tic_label, date)
        print(tic_label + ' (index, prix) : ' + format_Wh_price_pair(day_sum_00_to_23))    

# Affiche toutes les consommations horaires et prix entre 00:00 et
# 23:00, pour un jour donné
def print_hour_cons_between_23_and_00_TIC_all(date):
    print(date.strftime("\n%Y-%m-%d 00:00 calculée (<=> dans csv ou graphe %d/%m/%Y 23h)"))
    for tic_label in TIC_label_order:
        hourTIC = hour_cons_between_23_and_00_TIC(tic_label, date)
        print(tic_label + ' (conso, prix) : ' + format_Wh_price_pair(hourTIC))

#
# Fonctions pour gérer le fichier de configuration globale
#

# Télécharge le fichier de configuration globale depuis l'Ecodevice, le
# sauvegarde sous le nom de fichier donné et charge son contenu en
# mémoire
def download_globalConf_file(fullfilename):
    global arrGlobalConf

    print('Téléchargement en cours...')
    response = requests.get('http://' + ecodevice + '/admin/download/system.gce')
    if not response.status_code == 200:
        print('Le téléchargement a échoué. Erreur : ' + str(response.status_code))
        return
    with open(fullfilename, "wb") as outfile:
        outfile.write(response.content)
    arrGlobalConf=bytearray(response.content)

# Charge le fichier de configuration globale en mémoire
def load_globalConf_file(fullfilename):
    global arrGlobalConf
    
    with open(fullfilename, "rb") as infile:
        content=infile.read()
    arrGlobalConf=bytearray(content)    

# Ecrit le contenu (modifié) en mémoire dans un nouveau fichier dont le nom est donné
def write_globalConf_file(fullfilename):
        with open(fullfilename, "wb") as outfile:
            outfile.write(arrGlobalConf)

#
# Actions principales
#

def main():
    global arrGlobalConf # Configuration globale chargée en mémoire (bytearray)

    TICmeasures = [] # Liste des mesures TIC
    TICerrors = [] # Liste des mesures TIC avec marquage des incohérences trouvées

    #
    # Téléchargement de la configuration globale (ou travail sur un fichier existant)
    #  
    choice=input('Télécharger une sauvegarde globale depuis l\'Ecodevice ? [o/n]\n')
    if choice == 'o':
        config_filename = 'system_' + datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        fullfilename = workingdir + '/' + config_filename + '.gce'
        download_globalConf_file(fullfilename)
        print(f'Le fichier a été enregistré et nommé {fullfilename}')
    else: # Travail avec un fichier existant déjà téléchargé
        config_filename = existing_filename
        fullfilename = workingdir + '/' + config_filename + '.gce'
        choice=input(f'Utiliser le fichier {fullfilename} ? [o/n]\n')
        if not choice == 'o':
            return
        
    load_globalConf_file(fullfilename)

    #
    # Visualisation des erreurs dans des fichiers csv
    #

    # Définir ici l'intervalle de dates à visualiser
    # ----------------------------------------------

##    # Exemple
##    startDate=datetime.datetime(2024,1,4) # 04/01/2024
##    endDate=datetime.datetime(2024,1,6) # 06/01/2024

    startDate=datetime.datetime(2024,1,4)
    endDate=datetime.datetime(2024,1,6)

    # ----------------------------------------------
    
    # Export des mesures sur un intervalle de dates dans un fichier csv
    # Les index courants / prix cumulés sont exportés sur la dernière
    # ligne du fichier, avec une heure fictive (l'heure de la création
    # du fichier csv)
    # Les prix visualisés sont en cents dans le csv
    print('\nExport des mesures sélectionnées dans un fichier csv...')
    fullfilename = workingdir + '/' + config_filename + '_' + startDate.strftime('_du_%Y-%m-%d') + endDate.strftime('_au_%Y-%m-%d') + '.csv'
    TICmeasures=get_TICmeasures_all(startDate, endDate)
    outputTICmeasuresInCsv(TICmeasures, fullfilename)
    # Export des mesures avec marquage des erreurs dans un autre fichier
    # csv
    TICerrors=get_TICerrors(TICmeasures)
    fullfilename=workingdir + '/' + config_filename + '_' + startDate.strftime('_du_%Y-%m-%d') + endDate.strftime('_au_%Y-%m-%d') + '_erreurs.csv'
    outputTICmeasuresInCsv(TICerrors, fullfilename)
    print('\nLes mesures sélectionnées ont été exportées, pour visualiser les erreurs et définir les corrections.')

    #
    # Définir ici les corrections
    # Les prix sont à donner en euros
    # ---------------------------

    # Correction d'un index TIC courant (index et prix cumulé en euros)
##    # Exemple
##    update_current_TIC('HCJW', 222222, 111.11) # Nouvelles valeurs pour l'index courant HCJW


    # Définition des jours et/ou heures à corriger
##    # Exemple
##    janvier_4=datetime.datetime(2024,1,4,0) # 04/01/2024
##    janvier_5_4h=datetime.datetime(2024,1,5,4) # 05/01/2024 04:00 (peut être utilisé à la fois en tant que date - jour -  et heure)
    
    # Correction du relevé d'index pour certains index du 5 janvier (à 0h), prix en euros
##    # Exemple
##    update_day_TIC('HPJB', 8351707, 808.75, janvier_5_4h)
##    update_day_TIC('HCJR', 648775, 62.1, janvier_5_4h)
##    update_day_TIC('HPJR', 445733, 156.06, janvier_5_4h)

    # Correction du relevé conso horaire à 4h le 5 janvier (conso de 3h à 4h), prix en euros
##    # Exemple
##    update_hour_TIC('HCJB', 0, 0, janvier_5_4h)
##    update_hour_TIC('HPJB', 0, 0, janvier_5_4h)
##    update_hour_TIC('HCJW', 0, 0, janvier_5_4h)
##    update_hour_TIC('HPJW', 0, 0, janvier_5_4h)
##    update_hour_TIC('HCJR', 1522, 1.08, janvier_5_4h)
##    update_hour_TIC('HPJR', 0, 0, janvier_5_4h)
    
    # Correction du relevé d'index quotidien et de prix pour plusieurs jours et index TIC donnés, prix en euros
##    # Exemple
##    yesterday=datetime.datetime.now() - datetime.timedelta(days=1)
##    update_multiple_days_TIC('HPJB', 8351707, 808.75, janvier_4, yesterday)

    # ----------------------------------------------
    
    print('\nLes corrections ont été apportées en mémoire.')
    
    #
    # Visualisation des corrections dans les fichiers csv
    #

    # Export des mesures corrigées sur un intervalle de dates dans un fichier csv pour visualisation
    # Les prix visualisés sont en cents dans le csv
    print('\nExport des mesures sélectionnées dans un fichier csv...')
    fullfilename = workingdir + '/' + config_filename + '_' + startDate.strftime('_du_%Y-%m-%d') + endDate.strftime('_au_%Y-%m-%d') + '_après_correction.csv'
    TICmeasures=get_TICmeasures_all(startDate, endDate)
    outputTICmeasuresInCsv(TICmeasures, fullfilename)
    TICerrors=get_TICerrors(TICmeasures)
    fullfilename = workingdir + '/' + config_filename + '_' + startDate.strftime('_du_%Y-%m-%d') + endDate.strftime('_au_%Y-%m-%d') + '_erreurs_après_correction.csv'
    outputTICmeasuresInCsv(TICerrors, fullfilename)
    print('\nLes mesures sélectionnées ont été exportées, pour vérifier les corrections.')
    
    #
    # Sauvegarde dans un nouveau fichier ou ne rien faire pour l'instant
    #

    # Sauvegarde des corrections dans un nouveau fichier de configuration globale
    choice=input('\nValider maintenant les corrections ? Les modifications en cours vont être sauvegardées dans un nouveau fichier qui sera à importer manuellement. [o/n]\n')
    if choice == 'o':
        fullfilename = workingdir + '/' + config_filename + '_modifié_' + datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S") + '.gce'
        write_globalConf_file(fullfilename)
        print(f'\nModifications sauvegardées dans le fichier {fullfilename}')
        print('Restaurer la configuration globale manuellement dans l\'Ecodevice avec ce fichier.')


main()
