#!/usr/bin/env python3
""" ReformaterRapportTeams - convertir un fichier CSV de rapport Teams en informations utiles et lisibles
Licence: BSD 3 clauses (see https://opensource.org/licenses/BSD-3-Clause)
Auteur: Hubert Tournier
"""

import csv
import getopt
import logging
import os
import re
import signal
import sys

# Chaîne de version utilisée par les commandes what(1) et ident(1) :
ID = "@(#) $Id: ReformaterRapportTeams v1.0.1 (5 Février 2022) par Hubert Tournier $"

# Paramètres par défaut. Peuvent être redéfinis via la ligne de commande
parametres = {
    "Lister participants": True,
    "Afficher contenu": False,
}


################################################################################
def _initialisation_journalisation(nom_programme):
    """ Configuration de la journalisation """
    format_journal = nom_programme + ": %(levelname)s: %(message)s"
    logging.basicConfig(format=format_journal, level=logging.DEBUG)
    logging.disable(logging.INFO)


################################################################################
def _afficher_aide():
    """ Afficher le mode opératoire """
    print(file=sys.stderr)
    print("usage: ReformaterRapportTeams [--debug] [--aide|--help|-?] [--version]", file=sys.stderr)
    print("       [--lister|--list] [--voir|--show] [--] [fichier ...]", file=sys.stderr)
    print(
        "  ----------------  -------------------------------------------------",
        file=sys.stderr
    )
    print("  --lister|--list   Lister les participants de réunions [par défaut]", file=sys.stderr)
    print("  --voir|--show     Afficher le contenu du fichier de façon lisible", file=sys.stderr)
    print("  --debug           Activer traces de déverminage", file=sys.stderr)
    print("  --aide|--help|-?  Afficher ce message d'aide et sortir du programme", file=sys.stderr)
    print("  --version         Afficher la version et sortir du programme", file=sys.stderr)
    print("  --                Marqueur de fin d'options", file=sys.stderr)
    print(file=sys.stderr)


################################################################################
def _gestion_controle_c(signal_number, current_stack_frame):
    """ Ne pas afficher de stack trace sur contrôle-C """
    print(" Interrompu !\n", file=sys.stderr)
    _afficher_aide()
    sys.exit(1)


################################################################################
def _gestion_signaux():
    """ Gestion des signaux """
    signal.signal(signal.SIGINT, _gestion_controle_c)


################################################################################
def _gestion_ligne_commande():
    """ Gestion des arguments passés sur la ligne de commande """
    # pylint: disable=C0103
    global parametres
    # pylint: enable=C0103

    # Options reconnues :
    lettres_options = "?"
    chaines_options = [
        "aide",
        "debug",
        "help",
        "list",
        "lister",
        "show",
        "version",
        "voir",
    ]

    try:
        options, arguments_restants = getopt.getopt(
            sys.argv[1:], lettres_options, chaines_options
        )
    except getopt.GetoptError as erreur:
        logging.critical("Erreur de syntaxe : %s", erreur)
        _afficher_aide()
        sys.exit(1)

    for option, _ in options:

        if option in ("--lister", "--list"):
            parametres["Lister participants"] = True
            parametres["Afficher contenu"] = False

        elif option in ("--voir", "--show"):
            parametres["Afficher contenu"] = True
            parametres["Lister participants"] = False

        elif option == "--debug":
            logging.disable(logging.NOTSET)

        elif option in ("--aide", "--help", "-?"):
            _afficher_aide()
            sys.exit(0)

        elif option == "--version":
            print(ID.replace("@(" + "#)" + " $" + "Id" + ": ", "").replace(" $", ""))
            sys.exit(0)

    logging.debug("_gestion_ligne_commande(): arguments_restants:")
    logging.debug(arguments_restants)

    return arguments_restants


################################################################################
def decouper_audit_data(chaine):
    """ """
    audit_data = {}

    # On élimine les accolades en début et fin de chaîne
    chaine = chaine[1:-1]

    dans_champ = False
    dans_cle = False
    cle = ""
    dans_valeur = False
    valeur = ""
    for caractere in chaine:
        if dans_champ:
            if dans_cle:
                if caractere == '"':
                    dans_cle = False
                else:
                    cle += caractere
            elif dans_valeur:
                if type_valeur == None:
                    if caractere == '"':
                        type_valeur = "chaine"
                    elif caractere == '[':
                        type_valeur = "liste"
                    elif caractere >= "0" and caractere <= "9":
                        type_valeur = "nombre"
                        valeur += caractere
                    else:
                        logging.error("Caractere inattendu dans la valeur d'un champ : %s", caractere)
                        return None
                elif type_valeur == "chaine":
                    if caractere == '"':
                        cle_valeur = '{}="{}"'.format(cle, valeur)
                        audit_data[cle] = valeur
                        dans_valeur = False
                        dans_champ = False
                    else:
                        valeur += caractere
                elif type_valeur == "nombre":
                    if caractere >= "0" and caractere <= "9":
                        valeur += caractere
                    elif caractere == ',':
                        cle_valeur = '{}={}'.format(cle, valeur)
                        try:
                            audit_data[cle] = int(valeur)
                        except:
                            logging.error("Le champ numérique ne contient pas une valeur entière : %s", valeur)
                            return None
                        dans_valeur = False
                        dans_champ = False
                    else:
                        logging.error("Caractere inattendu dans la valeur numerique d'un champ : %s", caractere)
                        return None
                elif type_valeur == "liste":
                    if caractere == ']':
                        liste = decouper_audit_data(valeur)
                        cle_valeur = '{}="{}"'.format(cle, ",".join(liste))
                        audit_data[cle] = liste
                        dans_valeur = False
                        dans_champ = False
                    else:
                        valeur += caractere
            elif caractere == ':':
                dans_valeur = True
                type_valeur = None
                valeur = ""
            else:
                logging.error("Caractere inattendu dans le champ : %s", caractere)
                return None
        elif caractere == '"':
            dans_champ = True
            dans_cle = True
            cle = ""
        elif caractere == ',':
            dans_champ = False
        else:
            logging.error("Caractere inattendu hors champ : %s", caractere)
            return None

    return audit_data

################################################################################
def main():
    """ Point d'entrée du programme """
    nom_programme = os.path.basename(sys.argv[0])

    _initialisation_journalisation(nom_programme)
    _gestion_signaux()
    arguments = _gestion_ligne_commande()

    exit_status = 0

    if arguments:
        for argument in arguments:
            if os.path.isfile(argument):
                # Traitement du fichier :
                with open(argument, "r") as fichier:
                    lecteur = csv.reader(fichier)
                    lignes = list(lecteur)
                    numero_ligne = 1
                    for ligne in lignes:
                        # si l'on n'est pas sur la ligne d'en-têtes :
                        if ligne[0] != "CreationDate":
                            if ligne[2] != "MeetingParticipantDetail":
                                logging.warning("Ligne {} : 'Operations' différent de 'MeetingParticipantDetail' : {}".format(numero_ligne, ligne[2]))
    
                            details = decouper_audit_data(ligne[3])
    
                            if parametres["Lister participants"]:
                                chaine = ""
                                if "MeetingDetailId" in details:
                                    chaine += details["MeetingDetailId"]
                                chaine += ","
                                if "Attendees" in details:
                                    if "UserObjectId" in details["Attendees"]:
                                        chaine += details["Attendees"]["UserObjectId"]
                                chaine += ","
                                if "JoinTime" in details:
                                    chaine += details["JoinTime"]
                                chaine += ","
                                if "LeaveTime" in details:
                                    chaine += details["LeaveTime"]
                                chaine += ","
                                if "ClientIP" in details:
                                    chaine += details["ClientIP"]
                                chaine += ","
                                if "DeviceInformation" in details:
                                    chaine += details["DeviceInformation"].replace(",", " ")
                                print(chaine)
                                
                            elif parametres["Afficher contenu"]:
                                print("CreationDate={}".format(ligne[0]))
                                print("UserIds={}".format(ligne[1]))
                                print("Operations={}".format(ligne[2]))
                                print("AuditData:")
                                for cle in details.keys():
                                    if isinstance(details[cle], str):
                                        print("  " + cle + "=" + details[cle])
                                    elif isinstance(details[cle], int):
                                        print("  " + cle + "=" + str(details[cle]))
                                    elif isinstance(details[cle], dict):
                                        print("  " + cle + ":")
                                        for sous_cle in details[cle].keys():
                                            if isinstance(details[cle][sous_cle], str):
                                                print("    " + sous_cle + "=" + details[cle][sous_cle])
                                            elif isinstance(details[cle][sous_cle], int):
                                                print("    " + sous_cle + "=" + str(details[cle][sous_cle]))

                        numero_ligne += 1
            else:
                logging.error("'%s' n'est pas un nom de fichier", argument)
                exit_status += 1
    else:
        # Traitement des données sur l'entrée standard :
        # TODO (éventuellement...)
        pass

    sys.exit(exit_status)


if __name__ == "__main__":
    main()
