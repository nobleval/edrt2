""" Ce script fournit deux possibilités pour récupérer l'historique des
données météo X-THL depuis un Ecodevice RT2 : soit via le fichier de
configuration, soit directement par des requêtes HTTP (les mêmes que
celles qui servent à afficher les graphes). Les données présentes sont
exportées dans un fichier csv.

Se référer au readme.

Publié sur https://github.com/nobleval
@Author: nobleval
"""

import requests
import json
import datetime
import ast
import csv

#
# Données personnelles à modifier
#

# Adresse IP de l'ecodevice
ecodevice='192.168.1.19'

# Répertoire des sauvegardes de la configuration et de travail
workingdir= 'D:/My Documents/~Perso/2023/gce config'

# Nom du fichier de sauvegarde de la configuration déjà téléchargé sur
# lequel travailler (si il existe), sans extension .gce. Peut être une
# configuration seule, ou une configuration globale (les données X-THL
# se trouvent dans la partie configuraton, et non dans la partie
# historique)
existing_filename = 'config_2024-01-30T15-31-26'

#
# Autres données
#

# Correspondance entre les codes dans l'Ecodevice et les champs des données météo
weatherField={'200': 'X-THL 0 Temp', '201': 'X-THL 0 Hum', '202': 'X-THL 0 Lum', '203': 'X-THL 1 Temp', '204': 'X-THL 1 Hum', '205': 'X-THL 1 Lum'}

# Configuration seule ou configuration globale
configAPI={'config': 'config', 'global': 'system'}

#
# Fonctions pour extraire les données météo depuis le fichier de
# configuration
#

# Position des données météo
weatherPosition = 0x060000
#endWeatherPosition = ??

# Tailles
dataLength = 2
weatherHourLength = 4 * 16

# Offset
dataOffset = 4 # depuis position d'une heure

# Retourne l'heure lue à une position donnée
def hourFromBytes(hourPosition):
    year = 2000 + int.from_bytes(arrConfig[hourPosition:hourPosition+1], byteorder='big')
    month = int.from_bytes(arrConfig[hourPosition+1:hourPosition+2], byteorder='big')
    day = int.from_bytes(arrConfig[hourPosition+2:hourPosition+3], byteorder='big')
    hour = int.from_bytes(arrConfig[hourPosition+3:hourPosition+4], byteorder='big')
    try:
        h = datetime.datetime(year,month,day,hour,0)
    except:
        # absence d'heure ("trou" possible ou fin des mesures ?)
        # heure arbitraire retournée 01/01/2000 00:00
        return datetime.datetime(2000,1,1,0,0)
    return h

# Retourne la liste des données météo par heure
def getWeatherFromConfigFile():
    weather = []
    hourPosition = weatherPosition
    h = hourFromBytes(hourPosition)
    while h.year > 2000: # récupération des données tant qu'une absence d'heure n'est pas identifiée (considérée ici comme fin des mesures)
        dic = {}
        dic['Heure'] = f'{h:%Y-%m-%d %H:00}'
        dataPosition = hourPosition + dataOffset
        for field in weatherField.values():
            value = int.from_bytes(arrConfig[dataPosition:dataPosition+dataLength], byteorder='big')
            if field.endswith('Temp'):
                dic[field] = f'{(value * 175.72)/65535 - 46.85:.2f}'
            if field.endswith('Hum'):
                dic[field] = f'{(value * 125)/65535 - 6:.2f}'
            if field.endswith('Lum'):
                dic[field] = value                
            dataPosition = dataPosition+dataLength
        weather.append(dic)
        hourPosition = hourPosition + weatherHourLength
        h = hourFromBytes(hourPosition)
    return weather

#
# Fonctions pour gérer le fichier de configuration
#

# Télécharge le fichier de configuration seule depuis l'Ecodevice, le
# sauvegarde sous le nom de fichier donné et charge son contenu en
# mémoire
def downloadConfigfile(fullfilename, configType):
    global arrConfig

    print('Téléchargement en cours...')
    response = requests.get('http://' + ecodevice + '/admin/download/' + configAPI[configType] + '.gce')
    if not response.status_code == 200:
        print('Le téléchargement a échoué. Erreur : ' + str(response.status_code))
        return
    with open(fullfilename, "wb") as outfile:
        outfile.write(response.content)
    arrConfig=bytearray(response.content)

# Charge le fichier de configuration en mémoire
def loadConfigFile(fullfilename):
    global arrConfig
    
    with open(fullfilename, "rb") as infile:
        content=infile.read()
    arrConfig=bytearray(content)

# Permet de sélectionner le fichier de configuration et le charger en mémoire
def selectAndLoadConfigFile():
    # Téléchargement de la configuration (ou travail sur un fichier existant)
    configType = 'config'
    choice=input('Télécharger une configuration depuis l\'Ecodevice ? [o/n]\n')
    if choice == 'o':
        config_filename = configType + '_' + datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        fullfilename = workingdir + '/' + config_filename + '.gce'
        downloadConfigfile(fullfilename, configType)
        print(f'Le fichier a été enregistré et nommé {fullfilename}')
    else: # Travail avec un fichier existant déjà téléchargé (configuration seule ou configuration globale)
        config_filename = existing_filename
        fullfilename = workingdir + '/' + config_filename + '.gce'
        choice=input(f'Utiliser le fichier {fullfilename} ? [o/n]\n')
        if not choice == 'o':
            return        
        loadConfigFile(fullfilename)

#
# Fonctions pour extraire les données météo depuis l'Ecodevice
#

# Exclut les dates dans le futur
def exclude_datetime_in_the_future(pair):
        key, value = pair
        return(key <= datetime.datetime.now())

# Retourne les données météo par champ
def getWeatherByField(startDate, field):
        measure={}        
        endDate = datetime.datetime.now()
        deltaDate = datetime.timedelta(days=3) # une requête pour 3 jours
        iteratedDate = startDate + datetime.timedelta(days=1) # J-1, J, J+1
        while (iteratedDate <= endDate + datetime.timedelta(days=1)):
                param={'period': '1', 'startY': iteratedDate.year, 'startM': iteratedDate.month, 'startD': iteratedDate.day, 'opt': '2', 'target': field}
                response = requests.post('http://' + ecodevice + '/graph.json', data = param, headers = {'Content-Type': 'application/x-www-form-urlencoded'})
                if response.status_code == 200:
                        responseJson = response.json()
                        deltaTime = datetime.timedelta(hours=1)
                        startTime=iteratedDate - datetime.timedelta(days=1)
                        iteratedTime = startTime
                        try:
                                valueList = ast.literal_eval(responseJson['data'])
                        except:
                                # ignorer le champ
                                print(weatherField[field] + ' sera ignoré (valeurs absentes ou non conformes).')
                                return
                        for value in valueList:
                                measure[iteratedTime]=value
                                iteratedTime += deltaTime
                else:
                        print('La requête avec les paramètres ' + str(param) + ' a échouée (erreur HTTP ' + response.status_code + ')')
                iteratedDate += deltaDate                
        return measure

def getWeatherFromDevice(startDate):
        # donnée météo pour chaque champ 
        weatherByField={}
        for field in weatherField:
                weatherByField[field]=getWeatherByField(startDate, field)
        # toutes les données météo par heure     
        weather=[]
        for keyDateTime in dict(filter(exclude_datetime_in_the_future, weatherByField[next(iter(weatherField))].items())): # n'importe quel champ météo est utilisé en référence pour l'heure
                measure={}
                measure['Heure']=f'{keyDateTime:%Y-%m-%d %H:00}'
                for field in weatherField:
                        try:
                                measure[weatherField[field]]=weatherByField[field][keyDateTime]
                        except:
                                # ignorer les valeurs manquantes pour les champs ignorés
                                continue
                weather.append(measure)
        return weather 

#
# Fonctions d'export dans un fichier csv
#

# Exporte les données meteo dans un fichier csv
def outputWeatherInCsv(weather, fullfilename):
    # entête csv
    field_names = []
    field_names.append('Heure')
    for field in weatherField.values():
        field_names.append(field)
    delimiter = ';'
    # produit le fichier csv
    with open(fullfilename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, delimiter=delimiter, fieldnames = field_names)
        writer.writeheader()
        writer.writerows(weather)
      
def main():
        global arrConfig # Configuration chargée en mémoire (bytearray)
        weather = [] # Données météo par heure

##        # Récupération des données météo à partir de l'Ecodevice        
##        # Date de début des données météo (pour l'export à partir de l'Ecodevice)
##        startDate = datetime.datetime(2024, 1, 15)
##        weather = getWeatherFromDevice(startDate)

        # Ou récupération des données à partir d'un fichier de config
        selectAndLoadConfigFile()
        weather = getWeatherFromConfigFile()

        # Export csv
        startDateTime = datetime.datetime.strptime(weather[0]['Heure'], '%Y-%m-%d %H:%M')
        endDateTime = datetime.datetime.strptime(weather[-1]['Heure'], '%Y-%m-%d %H:%M')
        filename = 'Historique_X-THL_' + startDateTime.strftime('_du_%Y-%m-%d_%H-%M') + endDateTime.strftime('_au_%Y-%m-%d_%H-%M')
        fullfilename=workingdir + '/' + filename + '.csv'
        outputWeatherInCsv(weather, fullfilename)
        
main()


