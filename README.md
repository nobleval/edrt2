# configfile.py

Ce script fournit des fonctions pour lire et modifier des relevés de
l'historique d'un fichier de configuration globale exporté ou téléchargé
depuis un Ecodevice RT2, par exemple pour effectuer des corrections. Il
permet aussi de lire et modifier les index courants. A ce stade les
données lues et modifiables se limitent aux 7 index TIC (et prix
associés). Dans le script les index peuvent être accédés par leur nom
défini dans le dictionnaire *TIC_label_order* (n° d'ordre d'index de 0 à
6). Ces noms sont propres au script et n'ont pas besoin d'être les mêmes
que ceux définis dans l'Ecodevice (des noms courts sont les meilleurs
pour minimiser la largeur des colonnes dans le fichier csv d'export qui
permet de visualiser un extrait de l'historique).

Les relevés modifiables sont ceux disponibles dans l'historique, c'est à
dire les relevés quotidiens des index à 0h, les consommations horaires
relevées de 1h à 23h. La consommation horaire à 0h n'est pas enregistrée
mais peut être obtenue par calcul de la différence entre la différence
des index quotidiens de 2 jours consécutifs et la somme des
consommations de 0h à 23h (relevés de 1h à 23h).

Les corrections se passent en plusieurs temps :

1. D'abord télécharger le fichier de configuration (manuellement ou via
la fonction du script).
2. Travailler à partir du fichier téléchargé et définir manuellement les
corrections en appelant les fonctions disponibles dans le script et en
faisant autant d'essais ou de passes que nécessaire, visualiser les
problèmes et les corrections à l'aide des fichiers csv générés (pour un
intervalle de dates données) ou des fonctions d'affichage dans la
console. En pratique corriger d'abord les relevés d'index quotidien et
ensuite les consommations horaires. Les corrections sont uniquement
appliquées aux données en mémoire et ne modifient pas le fichier
original téléchargé.
3. Une fois que les corrections sont validées, exécuter une dernière
fois le script finalisé qui téléchargera le fichier de configuration
depuis l'Ecodevice, appliquera les corrections et les sauvegardera dans
un nouveau fichier de configuration. Charger ensuite immédiatement ce
fichier dans l'Ecodevice manuellement par la fonction de restauration de
la configuration globale.

> [!CAUTION]
> 
> Faire cette dernière opération **bien après** ou **bien avant** une
> heure ronde pour éviter un problème de relevé au moment où la
> configuration est mise à jour et que l'Ecodevice redémarre !

> [!NOTE]
> 
> 1. Le script n'agit pas sur les données situées dans l'Ecodevice. Il
> fabrique uniquement un nouveau fichier de configuration globale à partir
> d'un fichier existant.
> 2. En cas de problème de restauration, restaurer le fichier original
> téléchargé.
> 3. Les heures enregistrées sont les heures des relevés, alors que les
> heures dans les graphes et exports de l'Ecodevice sont les heures de
> début des périodes horaires (la consommation relevée à 20:00 est
> affichée à 19h par l'Ecodevice).
> 4. Le relevé quotidien à "minuit" du jour courant correspond au relevé à
> l'heure 00:00 du jour suivant
> 5. Le script a été expérimenté uniquement pour la version **3.00.04**
> (logiciel et firmware).

> [!NOTE]
> Limitations
> 
> 1. Mot de passe administrateur non pris en charge pour le téléchargement
> de la configuration

## Exemple d'extrait du fichier csv produit

![Extrait fichier csv!](/Visu_histo_relevés_et_calculs.png "Extrait fichier csv")
