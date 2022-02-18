#!/usr/bin/env python3
""" tala - Teams Audit Log Analyzer
Licence: BSD 3 clauses (see https://opensource.org/licenses/BSD-3-Clause)
Auteur: Hubert Tournier
"""

import csv
import datetime
import getopt
import logging
import os
import re
import signal
import sys

# Chaîne de version utilisée par les commandes what(1) et ident(1) :
ID = "@(#) $Id: tala - Teams Audit Log Analyzer v2.0.1 (18 Février 2022) par Hubert Tournier $"

# Paramètres par défaut. Peuvent être redéfinis via la ligne de commande
parametres = {
    "Afficher contenu": True,
    "Lister organisateurs": False,
    "Lister participants": False,
    "Lister deconnexions": False,
    "Base utilisateurs": "",
    "Filtre adresses": None,
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
    print("usage: tala [--debug] [--help|-?] [--version]", file=sys.stderr)
    print("       [-o|--organizers] [-a|--attendees]", file=sys.stderr)
    print("       [-u|--users FILE]", file=sys.stderr)
    print("       [-d|--disconnect] [-i|--ip REGEX]", file=sys.stderr)
    print("       [--] [file ...]", file=sys.stderr)
    print(
        "  ---------------  -------------------------------------------------",
        file=sys.stderr
    )
    print("  -o|--organizers  List meetings organizers", file=sys.stderr)
    print("  -a|--attendees   List meetings attendees", file=sys.stderr)
    print("  -d|--disconnect  List meetings disconnections", file=sys.stderr)
    print("  -i|--ip REGEX    Filter meeting disconnections by IP address regex", file=sys.stderr)
    print("  -u|--users FILE  create/update and use the FILE users database", file=sys.stderr)
    print("  --debug          Enable debug mode", file=sys.stderr)
    print("  --help|-?        Print usage and this help message and exit", file=sys.stderr)
    print("  --version        Print version and exit", file=sys.stderr)
    print("  --               Options processing terminator", file=sys.stderr)
    print(file=sys.stderr)


################################################################################
def _gestion_controle_c(signal_number, current_stack_frame):
    """ Ne pas afficher de stack trace sur contrôle-C """
    print(" Interrupted!\n", file=sys.stderr)
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
    lettres_options = "adi:ou:?"
    chaines_options = [
        "attendees",
        "debug",
        "disconnect",
        "help",
        "ip=",
        "organizers",
        "users=",
        "version",
    ]

    try:
        options, arguments_restants = getopt.getopt(
            sys.argv[1:], lettres_options, chaines_options
        )
    except getopt.GetoptError as erreur:
        logging.critical("Syntax error: %s", erreur)
        _afficher_aide()
        sys.exit(1)

    for option, argument in options:

        if option in ("-a", "--attendees"):
            parametres["Afficher contenu"] = False
            parametres["Lister organisateurs"] = False
            parametres["Lister participants"] = True
            parametres["Lister deconnexions"] = False

        elif option in ("-d", "--disconnect"):
            parametres["Afficher contenu"] = False
            parametres["Lister organisateurs"] = False
            parametres["Lister participants"] = False
            parametres["Lister deconnexions"] = True

        elif option in ("-i", "--ip"):
            try:
                parametres["Filtre adresses"] = re.compile(argument)
            except:
                logging.critical("'%s' is not a regular expression", argument)
                sys.exit(1)

        elif option in ("-o", "--organizers"):
            parametres["Afficher contenu"] = False
            parametres["Lister organisateurs"] = True
            parametres["Lister participants"] = False
            parametres["Lister deconnexions"] = False

        elif option in ("-u", "--users"):
            if os.path.isfile(argument):
                parametres["Base utilisateurs"] = argument
            else:
                logging.critical("'%s' is not a file", argument)
                sys.exit(1)

        elif option == "--debug":
            logging.disable(logging.NOTSET)

        elif option in ("--help", "-?"):
            _afficher_aide()
            sys.exit(0)

        elif option == "--version":
            print(ID.replace("@(" + "#)" + " $" + "Id" + ": ", "").replace(" $", ""))
            sys.exit(0)

    return arguments_restants


################################################################################
def decouper_audit_data(chaine):
    """ Parseur maison, pour garder l'imbrication des informations dans le journal """
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
                if type_valeur is None:
                    if caractere == '"':
                        type_valeur = "chaine"
                    elif caractere == '[':
                        type_valeur = "liste"
                    elif "0" <= caractere <= "9":
                        type_valeur = "nombre"
                        valeur += caractere
                    else:
                        logging.error("Caractere inattendu dans la valeur d'un champ : %s", caractere)
                        return None
                elif type_valeur == "chaine":
                    if caractere == '"':
                        audit_data[cle] = valeur
                        dans_valeur = False
                        dans_champ = False
                    else:
                        valeur += caractere
                elif type_valeur == "nombre":
                    if "0" <= caractere <= "9":
                        valeur += caractere
                    elif caractere == ',':
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
def convertir_secondes(chaine):
    """ Retourne le nombre de secondes écoulées depuis l'Epoch à partir d'une chaîne de date """
    return datetime.datetime.strptime(chaine, "%Y-%m-%dT%H:%M:%S").timestamp()


################################################################################
def extraire_reunions(fichier, afficher):
    """ Retourne des structures contenant la liste des réunions/organisateurs et des participants
        Vérifie au passage la présence de valeurs inhabituelles dans les champs """
    organisateurs = {}
    participants = {}

    lecteur = csv.reader(fichier)
    lignes = list(lecteur)
    numero_ligne = 1
    for ligne in lignes:

        # si l'on n'est pas sur la ligne d'en-têtes :
        if ligne[0][0] == "2": # TODO à améliorer
            if ligne[2] != "MeetingParticipantDetail":
                logging.warning("Ligne {} : 'Operations' différent de 'MeetingParticipantDetail' : {}".format(numero_ligne, ligne[2]))

            details = decouper_audit_data(ligne[3])

            if afficher:
                print("Line #{}".format(numero_ligne))
                print("CreationDate={}".format(ligne[0]))
                print("UserIds={}".format(ligne[1]))
                print("Operations={}".format(ligne[2]))
                if ligne[2] != "MeetingParticipantDetail":
                    logging.info("Ligne {} : 'Operations' différent de 'MeetingParticipantDetail': {}".format(numero_ligne, ligne[2]))
                print("AuditData:")
                for cle in details:
                    if isinstance(details[cle], str):
                        print("  " + cle + "=" + details[cle])
                        if cle == "Operation" and details[cle] != "MeetingParticipantDetail":
                            logging.info("Ligne {} : 'Operation' différent de 'MeetingParticipantDetail': {}".format(numero_ligne, details[cle]))
                        if cle == "Workload" and details[cle] != "MicrosoftTeams":
                            logging.info("Ligne {} : 'Workload' différent de 'MicrosoftTeams': {}".format(numero_ligne, details[cle]))
                        if cle == "ArtifactSharedName" and details[cle] != "videoTransmitted":
                            logging.info("Ligne {} : 'ArtifactSharedName' différent de 'videoTransmitted': {}".format(numero_ligne, details[cle]))
                        if cle == "Key" and details[cle] != "UserAgent":
                            logging.info("Ligne {} : 'Key' différent de 'UserAgent': {}".format(numero_ligne, details[cle]))
                        if cle == "RecipientType" and details[cle] not in ("User", "Anonymous", "Applications", "Phone"):
                            logging.info("Ligne {} : 'RecipientType' différent des valeurs connues: {}".format(numero_ligne, details[cle]))
                        if cle == "ItemName" and details[cle] not in ("ScheduledMeeting", "RecurringMeeting", "Escalation", "AdHocMeeting", "ChannelMeeting", "MicrosoftTeams", "Complete", "Broadcast", "ScreenSharingCall", "31"):
                            logging.info("Ligne {} : 'ItemName' différent des valeurs connues: {}".format(numero_ligne, details[cle]))

                    elif isinstance(details[cle], int):
                        print("  " + cle + "=" + str(details[cle]))
                        if cle == "RecordType" and details[cle] != 25:
                            logging.info("Ligne {} : 'RecordType' différent de 25: {}".format(numero_ligne, details[cle]))
                        if cle == "UserType" and details[cle] != 0:
                            logging.info("Ligne {} : 'UserType' différent de 0: {}".format(numero_ligne, details[cle]))
                        if cle == "Version" and details[cle] != 1:
                            logging.info("Ligne {} : 'Version' différent de 1: {}".format(numero_ligne, details[cle]))

                    elif isinstance(details[cle], dict):
                        print("  " + cle + ":")
                        for sous_cle in details[cle]:
                            if isinstance(details[cle][sous_cle], str):
                                print("    " + sous_cle + "=" + details[cle][sous_cle])
                            elif isinstance(details[cle][sous_cle], int):
                                print("    " + sous_cle + "=" + str(details[cle][sous_cle]))
                print()

            id_reunion = ""
            id_organisateur = ""
            email_organisateur = ""
            id_organisation_organisateur = ""
            type_reunion = ""
            id_participant = ""
            libelle_participant = ""
            cle_participant = ""
            type_cle = ""
            id_organisation_participant = ""
            debut = ""
            fin = ""
            adresse_ip = ""
            materiel = ""
            propriete = ""

            if "MeetingDetailId" in details:
                id_reunion = details["MeetingDetailId"]
            else:
                logging.warning("Ligne {} : 'MeetingDetailId' absent".format(numero_ligne))

            if "UserId" in details:
                email_organisateur = details["UserId"]
            else:
                logging.info("Ligne {} : 'UserId' absent".format(numero_ligne))

            if "UserKey" in details:
                id_organisateur = details["UserKey"]
            else:
                logging.info("Ligne {} : 'UserKey' absent".format(numero_ligne))

            if "OrganizationId" in details:
                id_organisation_organisateur = details["OrganizationId"]
            else:
                logging.info("Ligne {} : 'OrganizationId' absent".format(numero_ligne))

            if "ItemName" in details:
                type_reunion = details["ItemName"]
            else:
                logging.info("Ligne {} : 'ItemName' absent".format(numero_ligne))

            if "Attendees" in details:
                if "RecipientType" in details["Attendees"]:
                    type_cle = details["Attendees"]["RecipientType"]
                else:
                    logging.warning("Ligne {} : 'Attendees/RecipientType' absent".format(numero_ligne))

                if "UserObjectId" in details["Attendees"]:
                    id_participant = details["Attendees"]["UserObjectId"]
                    cle_participant = id_participant

                    if "OrganizationId" in details["Attendees"]:
                        id_organisation_participant = details["Attendees"]["OrganizationId"]

                elif "DisplayName" in details["Attendees"]:
                    libelle_participant = details["Attendees"]["DisplayName"]
                    cle_participant = libelle_participant
                else:
                    logging.warning("Ligne {} : 'Attendees/UserObjectid-DisplayName' absents".format(numero_ligne))
            else:
                logging.warning("Ligne {} : 'Attendees' absent".format(numero_ligne))

            if "ExtraProperties" in details:
                if "Value" in details["ExtraProperties"]:
                    propriete = details["ExtraProperties"]["Value"]
                    propriete = re.sub(r" \(.*", "", propriete)
                    propriete = re.sub(r"SkypeSpaces.*", "SkypeSpaces", propriete)
                    propriete = re.sub(r"^[0-9].*", "Some Agent", propriete)

            if "JoinTime" in details:
                debut = details["JoinTime"]
            else:
                logging.warning("Ligne {} : 'JoinTime' absent".format(numero_ligne))

            if "LeaveTime" in details:
                fin = details["LeaveTime"]
            else:
                logging.warning("Ligne {} : 'LeaveTime' absent".format(numero_ligne))

            if "ClientIP" in details:
                adresse_ip = details["ClientIP"]
            else:
                logging.info("Ligne {} : 'ClientIP' absent".format(numero_ligne))

            if "DeviceInformation" in details:
                materiel = details["DeviceInformation"].replace(",", " ")
            else:
                logging.info("Ligne {} : 'DeviceInformation' absent".format(numero_ligne))

            if id_reunion in organisateurs:
                if email_organisateur != organisateurs[id_reunion]["email_organisateur"]:
                    logging.warning("Ligne {} : 'email_organisateur' modifié pour la réunion: ".format(numero_ligne, id_reunion))
                if id_organisateur != organisateurs[id_reunion]["id_organisateur"]:
                    logging.warning("Ligne {} : 'id_organisateur' modifié pour la réunion: ".format(numero_ligne, id_reunion))
                if id_organisation_organisateur != organisateurs[id_reunion]["id_organisation"]:
                    logging.warning("Ligne {} : 'id_organisation_organisateur' modifié pour la réunion: ".format(numero_ligne, id_reunion))
                if type_reunion != organisateurs[id_reunion]["type_reunion"]:
                    logging.warning("Ligne {} : 'type_reunion' modifié pour la réunion: ".format(numero_ligne, id_reunion))
                secondes = convertir_secondes(debut)
                if secondes < 0:
                    logging.error("Ligne {} : 'debut' incorrect: ".format(numero_ligne, debut))
                elif secondes < convertir_secondes(organisateurs[id_reunion]["premier_arrive"]):
                    organisateurs[id_reunion]["premier_arrive"] = debut
                secondes = convertir_secondes(fin)
                if secondes < 0:
                    logging.error("Ligne {} : 'fin' incorrect: ".format(numero_ligne, fin))
                elif secondes > convertir_secondes(organisateurs[id_reunion]["dernier_parti"]):
                    organisateurs[id_reunion]["dernier_parti"] = fin
                if cle_participant not in organisateurs[id_reunion]["participants"]:
                    organisateurs[id_reunion]["participants"].append(cle_participant)
            else:
                # Nouvelle réunion
                details_reunion = {}
                details_reunion["email_organisateur"] = email_organisateur
                details_reunion["id_organisateur"] = id_organisateur
                details_reunion["id_organisation"] = id_organisation_organisateur
                details_reunion["type_reunion"] = type_reunion
                details_reunion["premier_arrive"] = debut
                details_reunion["dernier_parti"] = fin
                details_reunion["participants"] = [cle_participant]
                organisateurs[id_reunion] = details_reunion

            if id_reunion in participants:
                if cle_participant in participants[id_reunion]:
                    i = 0
                    doublon = False
                    while i < len(participants[id_reunion][cle_participant]):
                        if debut == participants[id_reunion][cle_participant][i]["debut"] \
                        and fin == participants[id_reunion][cle_participant][i]["fin"] \
                        and adresse_ip == participants[id_reunion][cle_participant][i]["adresse_ip"] \
                        and materiel == participants[id_reunion][cle_participant][i]["materiel"] \
                        and propriete == participants[id_reunion][cle_participant][i]["propriete"] \
                        and type_cle == participants[id_reunion][cle_participant][i]["type_cle"] \
                        and id_organisation_participant == participants[id_reunion][cle_participant][i]["id_organisation"]:
                            doublon = True
                            break

                        # On va trier les connexions par heure de début, puis par heure de fin :
                        secondes_debut_nouveau = convertir_secondes(debut)
                        secondes_debut_element = convertir_secondes(participants[id_reunion][cle_participant][i]["debut"])
                        if secondes_debut_nouveau < secondes_debut_element:
                            break
                        elif secondes_debut_nouveau == secondes_debut_element:
                            secondes_fin_nouveau = convertir_secondes(fin)
                            secondes_fin_element = convertir_secondes(participants[id_reunion][cle_participant][i]["fin"])
                            if secondes_fin_nouveau <= secondes_fin_element:
                                break

                        i += 1

                    if not doublon:
                        # Nouvelle connexion du participant à la réunion
                        details_connexion = {}
                        details_connexion["type_cle"] = type_cle
                        details_connexion["id_organisation"] = id_organisation_participant
                        details_connexion["debut"] = debut
                        details_connexion["fin"] = fin
                        details_connexion["adresse_ip"] = adresse_ip
                        details_connexion["materiel"] = materiel
                        details_connexion["propriete"] = propriete

                        # insertion triée :
                        participants[id_reunion][cle_participant] = participants[id_reunion][cle_participant][:i] \
                                                                    + [details_connexion] \
                                                                    +  participants[id_reunion][cle_participant][i:]
                else:
                    # Nouveau participant à la réunion
                    details_connexion = {}
                    details_connexion["type_cle"] = type_cle
                    details_connexion["id_organisation"] = id_organisation_participant
                    details_connexion["debut"] = debut
                    details_connexion["fin"] = fin
                    details_connexion["adresse_ip"] = adresse_ip
                    details_connexion["materiel"] = materiel
                    details_connexion["propriete"] = propriete
                    participants[id_reunion][cle_participant] = [details_connexion]
            else:
                # Nouvelle réunion
                details_connexion = {}
                details_connexion["type_cle"] = type_cle
                details_connexion["id_organisation"] = id_organisation_participant
                details_connexion["debut"] = debut
                details_connexion["fin"] = fin
                details_connexion["adresse_ip"] = adresse_ip
                details_connexion["materiel"] = materiel
                details_connexion["propriete"] = propriete
                participant = {cle_participant: [details_connexion]}
                participants[id_reunion] = participant

        numero_ligne += 1

    return organisateurs, participants


################################################################################
def charger_uids(nom_fichier):
    """ Construit un dictionnaire UID: EMAIL à partir d'un fichier CSV UID,EMAIL """
    uids = {}
    with open(nom_fichier, "r", encoding="utf-8") as fichier:
        for ligne in fichier.readlines():
            champs = ligne.strip().split(",")
            uids[champs[0]] = champs[1]
    return uids


################################################################################
def mettre_a_jour_uids(nom_fichier, organisateurs, uids):
    """ Met à jour le fichier CSV UID,EMAIL à partir du dictionnaire """
    nouveaux_uids = False
    for id_reunion in organisateurs:
        if organisateurs[id_reunion]["id_organisateur"] not in uids:
            uids[organisateurs[id_reunion]["id_organisateur"]] = organisateurs[id_reunion]["email_organisateur"]
            nouveaux_uids = True

    if nouveaux_uids:
        with open(nom_fichier, "w", encoding="utf-8") as fichier:
            for uid in uids:
                fichier.write(
                    "{:s},{:s}\n".format(
                        uid,
                        uids[uid],
                    )
                )

    return uids


################################################################################
def lister_organisateurs(reunions):
    """ Lister les réunions au format CSV """
    print("#meeting_id,organizer_email,organizer_id,organizer_organization,meeting_type,first_join,last_leave,number_attendees")
    for id_reunion in reunions:
        print(
            "{:s},{:s},{:s},{:s},{:s},{:s},{:s},{:d}".format(
                id_reunion,
                reunions[id_reunion]["email_organisateur"],
                reunions[id_reunion]["id_organisateur"],
                reunions[id_reunion]["id_organisation"],
                reunions[id_reunion]["type_reunion"],
                reunions[id_reunion]["premier_arrive"],
                reunions[id_reunion]["dernier_parti"],
                len(reunions[id_reunion]["participants"]),
            )
        )


################################################################################
def lister_participants(reunions):
    """ Lister les connexions des participants de réunions au format CSV """
    print("#meeting_id,attendee_key,key_type,attendee_organization,join_time,leave_time,client_ip,device,property")
    for id_reunion in reunions:
        for cle_participant in reunions[id_reunion]:
            for connexion in reunions[id_reunion][cle_participant]:
                print(
                    "{:s},{:s},{:s},{:s},{:s},{:s},{:s},{:s},{:s}".format(
                        id_reunion,
                        cle_participant,
                        connexion["type_cle"],
                        connexion["id_organisation"],
                        connexion["debut"],
                        connexion["fin"],
                        connexion["adresse_ip"],
                        connexion["materiel"],
                        connexion["propriete"],
                    )
                )


################################################################################
def lister_deconnexions(organisateurs, participants, uids, filtre):
    """ Liste les réunions/participants/connexions avec suspicion de déconnexion """
    for id_reunion in participants:
        infos_reunion = False
        for cle_participant in participants[id_reunion]:
            infos_participant = False
            if len(participants[id_reunion][cle_participant]) > 1:
                selectionne = False
                if filtre:
                    # on vérifie si au moins 1 des connexions est faite à partir d'une adresse filtrée :
                    for connexion in participants[id_reunion][cle_participant]:
                        if filtre.search(connexion["adresse_ip"]):
                            selectionne = True
                            break
                else:
                    selectionne = True

                if selectionne:
                    if not infos_reunion:
                        # Informations sur la réunion :
                        date_reunion = re.sub(r"T.*", "", organisateurs[id_reunion]["premier_arrive"])
                        debut_reunion = re.sub(r".*T", "", organisateurs[id_reunion]["premier_arrive"])
                        fin_reunion = re.sub(r".*T", "", organisateurs[id_reunion]["dernier_parti"])
                        print(
                            "Meeting ID: {:s} / Type: {:s} / Date: {:s} / Time: {:s} - {:s} / #Attendees: {:d}".format(
                                id_reunion,
                                organisateurs[id_reunion]["type_reunion"],
                                date_reunion,
                                debut_reunion,
                                fin_reunion,
                                len(organisateurs[id_reunion]["participants"]),
                            )
                        )
                        infos_reunion = True

                    # Information sur les participants:
                    if not infos_participant:
                        # Informations sur le participant :
                        if cle_participant in uids:
                            print(
                                "  Attendee: {:s} / Key type: {:s} / Email: {:s} / Organization ID: {:s}".format(
                                    cle_participant,
                                    participants[id_reunion][cle_participant][0]["type_cle"],
                                    uids[cle_participant],
                                    participants[id_reunion][cle_participant][0]["id_organisation"],
                                )
                            )
                        else:
                            print(
                                "  Attendee: {:s} / Key type: {:s} / Organization ID: {:s}".format(
                                    cle_participant,
                                    participants[id_reunion][cle_participant][0]["type_cle"],
                                    participants[id_reunion][cle_participant][0]["id_organisation"],
                                )
                            )
                        infos_participant = True

                    for connexion in participants[id_reunion][cle_participant]:
                        debut_connexion = re.sub(r".*T", "", connexion["debut"])
                        fin_connexion = re.sub(r".*T", "", connexion["fin"])
                        if connexion["propriete"] == 'CallSignalingAgent':
                            print(
                                "    Time: {:s} - {:s} / IP address: {:15s} / Device: {:s}".format(
                                    debut_connexion,
                                    fin_connexion,
                                    connexion["adresse_ip"],
                                    connexion["materiel"],
                                )
                            )
                        else:
                            print(
                                "    Time: {:s} - {:s} / IP address: {:15s} / Device: {:s} / Properties: {:s}".format(
                                    debut_connexion,
                                    fin_connexion,
                                    connexion["adresse_ip"],
                                    connexion["materiel"],
                                    connexion["propriete"],
                                )
                            )
                    print()


################################################################################
def main():
    """ Point d'entrée du programme """
    nom_programme = os.path.basename(sys.argv[0])

    _initialisation_journalisation(nom_programme)
    _gestion_signaux()
    arguments = _gestion_ligne_commande()

    exit_status = 0

    uids = {}
    if parametres["Base utilisateurs"]:
        uids = charger_uids(parametres["Base utilisateurs"])

    if arguments:
        for argument in arguments:
            if os.path.isfile(argument):
                # Traitement du fichier :
                with open(argument, "r", encoding="utf-8") as fichier:
                    organisateurs, participants = extraire_reunions(fichier, parametres["Afficher contenu"])

                    if parametres["Base utilisateurs"]:
                        uids = mettre_a_jour_uids(parametres["Base utilisateurs"], organisateurs, uids)

                    if parametres["Lister organisateurs"]:
                        lister_organisateurs(organisateurs)
                    elif parametres["Lister participants"]:
                        lister_participants(participants)
                    elif parametres["Lister deconnexions"]:
                        lister_deconnexions(organisateurs, participants, uids, parametres["Filtre adresses"])

            else:
                logging.error("'%s' is not a file name", argument)
                exit_status += 1
    else:
        # Traitement des données sur l'entrée standard :
        fichier = sys.stdin
        organisateurs, participants = extraire_reunions(fichier, parametres["Afficher contenu"])

        if parametres["Base utilisateurs"]:
            uids = mettre_a_jour_uids(parametres["Base utilisateurs"], organisateurs, uids)

        if parametres["Lister organisateurs"]:
            lister_organisateurs(organisateurs)
        elif parametres["Lister participants"]:
            lister_participants(participants)
        elif parametres["Lister deconnexions"]:
            lister_deconnexions(organisateurs, participants, uids, parametres["Filtre adresses"])

    sys.exit(exit_status)


if __name__ == "__main__":
    main()
